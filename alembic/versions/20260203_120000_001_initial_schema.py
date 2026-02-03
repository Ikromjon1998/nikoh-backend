"""Initial schema with all tables.

Revision ID: 001
Revises:
Create Date: 2026-02-03 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""

    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('preferred_language', sa.String(10), nullable=True, server_default='ru'),
        sa.Column('email_verified', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('verification_status', sa.String(20), nullable=True, server_default='unverified'),
        sa.Column('verification_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_unique_constraint('uq_users_phone', 'users', ['phone'])

    # Profiles table
    op.create_table(
        'profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Verified information (from documents)
        sa.Column('verified_first_name', sa.String(100), nullable=True),
        sa.Column('verified_last_initial', sa.String(10), nullable=True),
        sa.Column('verified_birth_date', sa.Date(), nullable=True),
        sa.Column('verified_nationality', sa.String(100), nullable=True),
        sa.Column('verified_residence_country', sa.String(100), nullable=True),
        sa.Column('verified_marital_status', sa.String(50), nullable=True),
        sa.Column('verified_education_level', sa.String(50), nullable=True),

        # Self-declared information
        sa.Column('gender', sa.String(20), nullable=False),
        sa.Column('seeking_gender', sa.String(20), nullable=True),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('height_cm', sa.Integer(), nullable=True),
        sa.Column('ethnicity', sa.String(50), nullable=True),
        sa.Column('marital_status', sa.String(50), nullable=True),
        sa.Column('has_children', sa.Boolean(), nullable=True),
        sa.Column('wants_children', sa.String(50), nullable=True),
        sa.Column('education_level', sa.String(50), nullable=True),
        sa.Column('occupation', sa.String(100), nullable=True),
        sa.Column('religious_practice', sa.String(50), nullable=True),
        sa.Column('languages', postgresql.ARRAY(sa.String(50)), nullable=True),

        # Location
        sa.Column('current_city', sa.String(100), nullable=True),
        sa.Column('current_country', sa.String(100), nullable=True),
        sa.Column('willing_to_relocate', sa.Boolean(), nullable=True, server_default='false'),

        # Lifestyle
        sa.Column('smoking', sa.String(50), nullable=True),
        sa.Column('alcohol', sa.String(50), nullable=True),
        sa.Column('diet', sa.String(50), nullable=True),

        # Essays
        sa.Column('about_me', sa.Text(), nullable=True),
        sa.Column('looking_for', sa.Text(), nullable=True),
        sa.Column('family_values', sa.Text(), nullable=True),

        # Visibility
        sa.Column('is_visible', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('show_online_status', sa.Boolean(), nullable=True, server_default='true'),

        # Profile completeness
        sa.Column('completeness_score', sa.Integer(), nullable=True, server_default='0'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_profiles_user_id', 'profiles', ['user_id'], unique=True)

    # Interests table
    op.create_table(
        'interests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),

        sa.ForeignKeyConstraint(['from_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_interests_from_user_id', 'interests', ['from_user_id'])
    op.create_index('ix_interests_to_user_id', 'interests', ['to_user_id'])
    op.create_unique_constraint('uq_interests_from_to', 'interests', ['from_user_id', 'to_user_id'])

    # Matches table
    op.create_table(
        'matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_a_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_b_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=True, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('unmatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unmatched_by', postgresql.UUID(as_uuid=True), nullable=True),

        sa.ForeignKeyConstraint(['user_a_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_b_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['unmatched_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('user_a_id < user_b_id', name='ck_matches_user_order'),
    )
    op.create_index('ix_matches_user_a_id', 'matches', ['user_a_id'])
    op.create_index('ix_matches_user_b_id', 'matches', ['user_b_id'])
    op.create_unique_constraint('uq_matches_users', 'matches', ['user_a_id', 'user_b_id'])

    # Verifications table
    op.create_table(
        'verifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('document_country', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('extracted_data', postgresql.JSON(), nullable=True),
        sa.Column('document_expiry_date', sa.Date(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('verification_method', sa.String(20), nullable=True),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_verifications_user_id', 'verifications', ['user_id'])

    # Selfies table
    op.create_table(
        'selfies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('face_embedding', sa.LargeBinary(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_selfies_user_id', 'selfies', ['user_id'], unique=True)

    # Payments table
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('verification_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(255), nullable=True),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('stripe_charge_id', sa.String(255), nullable=True),
        sa.Column('payment_type', sa.Enum('standard_verification', 'priority_verification', 'renewal_verification', name='paymenttype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'completed', 'failed', 'refunded', 'cancelled', name='paymentstatus'), nullable=False, server_default='pending'),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='eur'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verification_id'], ['verifications.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_payments_user_id', 'payments', ['user_id'])
    op.create_index('ix_payments_stripe_payment_intent_id', 'payments', ['stripe_payment_intent_id'], unique=True)

    # Search preferences table
    op.create_table(
        'search_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Age preferences
        sa.Column('min_age', sa.Integer(), nullable=False, server_default='18'),
        sa.Column('max_age', sa.Integer(), nullable=False, server_default='99'),

        # Location preferences
        sa.Column('preferred_countries', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('preferred_cities', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('willing_to_relocate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('relocation_countries', postgresql.ARRAY(sa.String(100)), nullable=True),

        # Background preferences
        sa.Column('preferred_ethnicities', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('preferred_marital_statuses', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('preferred_education_levels', postgresql.ARRAY(sa.String(50)), nullable=True),

        # Religion preferences
        sa.Column('preferred_religious_practices', postgresql.ARRAY(sa.String(50)), nullable=True),

        # Physical preferences
        sa.Column('min_height_cm', sa.Integer(), nullable=True),
        sa.Column('max_height_cm', sa.Integer(), nullable=True),

        # Lifestyle preferences
        sa.Column('preferred_smoking', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('preferred_alcohol', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('preferred_diet', postgresql.ARRAY(sa.String(50)), nullable=True),

        # Other preferences
        sa.Column('must_be_verified', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('has_children_acceptable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('children_preference', sa.String(50), nullable=True, server_default='no_preference'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),

        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_search_preferences_user_id', 'search_preferences', ['user_id'], unique=True)


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('search_preferences')
    op.drop_table('payments')
    op.drop_table('selfies')
    op.drop_table('verifications')
    op.drop_table('matches')
    op.drop_table('interests')
    op.drop_table('profiles')
    op.drop_table('users')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS paymenttype')
    op.execute('DROP TYPE IF EXISTS paymentstatus')
