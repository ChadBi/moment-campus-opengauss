from app.database import Base

from .user import User
from .school import School
from .post import Post
from .category import Category
from .post_image import PostImage
from .location import Location
from .comment import Comment
from .like import Like
from .validation_record import ValidationRecord
from .report import Report
from .notification import Notification
from .topic_collection import TopicCollection
from .topic_collection_post import TopicCollectionPost
from .draft import Draft
from .browse_history import BrowseHistory
from .search_history import SearchHistory
from .admin_operation_log import AdminOperationLog
from .school_membership import SchoolMembership
from .school_settings import SchoolSettings
from .school_domain import SchoolDomain
from .product_plan import ProductPlan
from .plan_entitlement import PlanEntitlement
from .school_subscription import SchoolSubscription
from .tenant_usage_daily import TenantUsageDaily
from .product_event import ProductEvent
from .platform_audit import PlatformAuditLog
from .password_reset_token import PasswordResetToken
from .ai_invocation_log import AIInvocationLog
from .job_run_record import JobRunRecord
from .notification_preference import NotificationPreference
from .subscription import UserSubscription
from .user_recommendation_preference import UserRecommendationPreference
from .user_auth_identity import UserAuthIdentity
from .auth_session import AuthSession, BindingTicket
from .location_review import LocationReview
from .campus_verify_token import CampusVerifyToken
from .sms_verification import SmsVerification
from .feedback import Feedback
from .location_fact import LocationFact, LocationFactProposal
from .location_summary import LocationSummaryVersion

__all__ = [
    "Base",
    "User",
    "School",
    "Post",
    "Category",
    "PostImage",
    "Location",
    "Comment",
    "Like",
    "ValidationRecord",
    "Report",
    "Notification",
    "TopicCollection",
    "TopicCollectionPost",
    "Draft",
    "BrowseHistory",
    "SearchHistory",
    "AdminOperationLog",
    "SchoolMembership",
    "SchoolSettings",
    "SchoolDomain",
    "ProductPlan",
    "PlanEntitlement",
    "SchoolSubscription",
    "TenantUsageDaily",
    "ProductEvent",
    "PlatformAuditLog",
    "PasswordResetToken",
    "AIInvocationLog",
    "JobRunRecord",
    "NotificationPreference",
    "UserSubscription",
    "UserAuthIdentity",
    "AuthSession",
    "BindingTicket",
    "LocationReview",
    "CampusVerifyToken",
    "SmsVerification",
    "Feedback",
    "LocationFact",
    "LocationFactProposal",
    "LocationSummaryVersion",
]
