import hashlib
import re

import pandas as pd

EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_RE = re.compile(r"\b(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Columns fully replaced with a marker
RESTRICTED_KEYWORDS = ("password", "ssn", "credit_card", "card", "secret", "token")
# Columns replaced with a stable pseudonym (still usable for counting / grouping)
PSEUDONYMIZE_COLUMNS = ("customer name", "retail sales people")


class PIISanitizer:
    @staticmethod
    def mask_text(text):
        if not isinstance(text, str):
            return text
        text = EMAIL_RE.sub("[EMAIL_REDACTED]", text)
        text = SSN_RE.sub("[SSN_REDACTED]", text)
        text = PHONE_RE.sub("[PHONE_REDACTED]", text)
        return text

    @staticmethod
    def pseudonym(value, prefix: str) -> str:
        if pd.isna(value):
            return value
        digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:6]
        return f"{prefix}-{digest}"

    @classmethod
    def sanitize_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col in out.columns:
            name = str(col).lower()
            if any(k in name for k in RESTRICTED_KEYWORDS):
                out[col] = "[RESTRICTED]"
            elif name in PSEUDONYMIZE_COLUMNS:
                prefix = "Person" if "people" in name else "Customer"
                out[col] = out[col].map(lambda v: cls.pseudonym(v, prefix))
            elif pd.api.types.is_string_dtype(out[col]) or out[col].dtype == object:
                out[col] = out[col].map(cls.mask_text)
        return out
