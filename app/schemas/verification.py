from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    passport = "passport"
    residence_permit = "residence_permit"
    divorce_certificate = "divorce_certificate"
    diploma = "diploma"
    employment_proof = "employment_proof"


class VerificationStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class VerificationMethod(str, Enum):
    automated = "automated"
    manual = "manual"


# Extracted data schemas by document type
class PassportData(BaseModel):
    first_name: str
    last_name: str
    birth_date: date
    birth_place: str | None = None
    nationality: str
    document_number: str
    expiry_date: date


class ResidencePermitData(BaseModel):
    permit_type: str
    country: str
    expiry_date: date
    status: str


class DivorceCertificateData(BaseModel):
    divorce_date: date
    country: str


class DiplomaData(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    graduation_date: date
    country: str


class EmploymentProofData(BaseModel):
    employer: str
    position: str
    start_date: date
    country: str


class VerificationCreate(BaseModel):
    """Data sent with file upload (form fields)"""

    document_type: DocumentType
    document_country: str = Field(..., max_length=100)


class VerificationResponse(BaseModel):
    """Verification details returned by API"""

    id: UUID
    user_id: UUID
    document_type: str
    document_country: str
    status: str
    rejection_reason: str | None
    extracted_data: dict | None
    document_expiry_date: date | None
    original_filename: str | None
    mime_type: str | None
    file_size: int | None
    verification_method: str | None
    created_at: datetime
    submitted_at: datetime | None
    verified_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class VerificationAdminResponse(VerificationResponse):
    """Admin view includes file path"""

    file_path: str | None
    verified_by: UUID | None


class VerificationListResponse(BaseModel):
    """Paginated list of verifications"""

    verifications: list[VerificationResponse]
    total: int
    page: int
    per_page: int


class VerificationAdminListResponse(BaseModel):
    """Paginated list of verifications for admin"""

    verifications: list[VerificationAdminResponse]
    total: int
    page: int
    per_page: int


class VerificationApprove(BaseModel):
    """Admin approval with extracted data"""

    extracted_data: dict
    document_expiry_date: date | None = None


class VerificationReject(BaseModel):
    """Admin rejection with reason"""

    reason: str = Field(..., min_length=10, max_length=1000)


class VerificationStatusSummary(BaseModel):
    """Summary of user's verification status"""

    overall_status: str  # unverified, partial, verified
    verified_documents: list[str]
    pending_documents: list[str]
    missing_required_documents: list[str]
    verification_expires_at: datetime | None
