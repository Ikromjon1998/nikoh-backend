"""
Seed script to populate database with test data for development/testing.
Run with: python scripts/seed_test_data.py
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from faker import Faker
from passlib.context import CryptContext

from app.database import async_session_maker
from app.models.user import User
from app.models.profile import Profile
from app.models.verification import Verification
from app.models.report import Report

fake = Faker()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration
NUM_USERS = 100
NUM_VERIFICATIONS = 30  # Pending/processing verifications
NUM_REPORTS = 15  # Open reports


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


async def seed_users(db) -> list[User]:
    """Create test users with various statuses."""
    users = []

    # Password for all test users (for easy login during testing)
    test_password_hash = hash_password("Test1234!")

    statuses = ["active", "active", "active", "active", "suspended", "banned", "pending"]
    verification_statuses = ["unverified", "unverified", "unverified", "partial", "verified", "verified"]
    languages = ["ru", "uz", "en"]

    print(f"Creating {NUM_USERS} test users...")

    for i in range(NUM_USERS):
        # Generate realistic data
        first_name = fake.first_name()
        last_name = fake.last_name()

        status = random.choice(statuses)
        verification_status = random.choice(verification_statuses)

        # If user is verified, set expiry date
        verification_expires = None
        if verification_status == "verified":
            verification_expires = datetime.now(timezone.utc) + timedelta(days=random.randint(30, 365))

        user = User(
            id=uuid4(),
            email=f"user{i+1}@test.nikoh.com",
            phone=f"+99890{random.randint(1000000, 9999999)}",
            password_hash=test_password_hash,
            status=status,
            verification_status=verification_status,
            preferred_language=random.choice(languages),
            email_verified=random.choice([True, True, True, False]),  # 75% verified
            is_admin=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 180)),
            last_active_at=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 720)),
            verification_expires_at=verification_expires,
        )
        db.add(user)
        users.append(user)

    await db.flush()
    print(f"  Created {len(users)} users")
    return users


async def seed_profiles(db, users: list[User]) -> list[Profile]:
    """Create profiles for test users with proper gender distribution."""
    profiles = []

    ethnicities = ["uzbek", "kazakh", "tajik", "kyrgyz", "turkmen", "tatar", "mixed", "other"]
    religious_practices = ["very_practicing", "practicing", "moderate", "cultural", "not_practicing"]
    marital_statuses = ["never_married", "divorced", "widowed"]
    education_levels = ["high_school", "bachelors", "masters", "phd", "other"]
    countries = ["Uzbekistan", "Kazakhstan", "Russia", "Germany", "USA", "Turkey", "UAE"]
    cities = ["Tashkent", "Samarkand", "Bukhara", "Almaty", "Moscow", "Berlin", "Istanbul"]

    print(f"Creating profiles for {len(users)} users...")

    for i, user in enumerate(users):
        # Alternate genders: even index = male, odd index = female
        gender = "male" if i % 2 == 0 else "female"
        seeking_gender = "female" if gender == "male" else "male"

        # Generate realistic birth date (18-50 years old)
        age = random.randint(18, 50)
        birth_date = datetime.now(timezone.utc).date() - timedelta(days=age * 365 + random.randint(0, 364))

        # Generate name based on gender
        if gender == "male":
            first_name = fake.first_name_male()
        else:
            first_name = fake.first_name_female()
        last_name = fake.last_name()

        profile = Profile(
            id=uuid4(),
            user_id=user.id,
            gender=gender,
            seeking_gender=seeking_gender,
            verified_first_name=first_name,
            verified_last_name=last_name,
            verified_last_initial=last_name[0] if last_name else None,
            verified_birth_date=birth_date,
            verified_residence_country=random.choice(countries),
            ethnicity=random.choice(ethnicities),
            religious_practice=random.choice(religious_practices),
            marital_status=random.choice(marital_statuses),
            education_level=random.choice(education_levels),
            current_city=random.choice(cities),
            height_cm=random.randint(155, 195) if gender == "male" else random.randint(150, 180),
            weight_kg=random.randint(60, 100) if gender == "male" else random.randint(45, 80),
            profession=fake.job()[:100],
            about_me=fake.paragraph(nb_sentences=4) if random.choice([True, False]) else None,
            ideal_partner=fake.paragraph(nb_sentences=3) if random.choice([True, False]) else None,
            is_visible=random.choice([True, True, True, False]),  # 75% visible
            profile_score=random.randint(40, 100),
            is_complete=random.choice([True, True, False]),  # 67% complete
            created_at=user.created_at,
        )
        db.add(profile)
        profiles.append(profile)

    await db.flush()
    print(f"  Created {len(profiles)} profiles")
    print(f"    - Male: {len([p for p in profiles if p.gender == 'male'])}")
    print(f"    - Female: {len([p for p in profiles if p.gender == 'female'])}")
    return profiles


async def seed_verifications(db, users: list[User]) -> list[Verification]:
    """Create pending verifications for some users."""
    verifications = []

    # Get users who are not fully verified
    unverified_users = [u for u in users if u.verification_status in ("unverified", "partial")]

    # Select random users for pending verifications
    users_to_verify = random.sample(unverified_users, min(NUM_VERIFICATIONS, len(unverified_users)))

    document_types = ["passport", "residence_permit", "divorce_certificate", "diploma", "employment_proof"]
    countries = ["Uzbekistan", "Russia", "Kazakhstan", "Germany", "USA", "Turkey", "UAE"]
    statuses = ["pending", "pending", "pending", "processing", "manual_review"]

    print(f"Creating {len(users_to_verify)} pending verifications...")

    for user in users_to_verify:
        doc_type = random.choice(document_types)

        verification = Verification(
            id=uuid4(),
            user_id=user.id,
            document_type=doc_type,
            document_country=random.choice(countries),
            status=random.choice(statuses),
            file_path=f"uploads/verifications/{uuid4()}.pdf",
            original_filename=f"{doc_type}_{fake.file_name(extension='pdf')}",
            mime_type="application/pdf",
            file_size=random.randint(100000, 5000000),
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 14)),
            submitted_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 7)),
        )
        db.add(verification)
        verifications.append(verification)

    await db.flush()
    print(f"  Created {len(verifications)} verifications")
    return verifications


async def seed_reports(db, users: list[User]) -> list[Report]:
    """Create reports between users."""
    reports = []

    # Get active users for reporters
    active_users = [u for u in users if u.status == "active"]

    if len(active_users) < 2:
        print("  Not enough active users for reports")
        return reports

    reasons = [
        "inappropriate_content",
        "harassment",
        "fake_profile",
        "scam",
        "spam",
        "other"
    ]

    statuses = ["pending", "pending", "pending", "reviewed", "dismissed", "action_taken"]

    print(f"Creating {NUM_REPORTS} reports...")

    for _ in range(NUM_REPORTS):
        # Pick reporter and reported user (must be different)
        reporter, reported = random.sample(active_users, 2)

        report = Report(
            id=uuid4(),
            reporter_user_id=reporter.id,
            reported_user_id=reported.id,
            reason=random.choice(reasons),
            description=fake.paragraph(nb_sentences=3) if random.choice([True, False]) else None,
            status=random.choice(statuses),
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30)),
        )
        db.add(report)
        reports.append(report)

    await db.flush()
    print(f"  Created {len(reports)} reports")
    return reports


async def main():
    print("=" * 50)
    print("Seeding test data for Nikoh Backend")
    print("=" * 50)

    async with async_session_maker() as db:
        try:
            # Check if test users already exist
            from sqlalchemy import select, func
            count_result = await db.execute(
                select(func.count(User.id)).where(User.email.like("%@test.nikoh.com"))
            )
            existing_count = count_result.scalar() or 0

            if existing_count > 0:
                print(f"\nFound {existing_count} existing test users.")
                response = input("Do you want to add more test data? (y/n): ")
                if response.lower() != 'y':
                    print("Aborted.")
                    return

            print("\nCreating test data...")

            # Seed data
            users = await seed_users(db)
            profiles = await seed_profiles(db, users)
            verifications = await seed_verifications(db, users)
            reports = await seed_reports(db, users)

            # Commit all changes
            await db.commit()

            # Print summary
            print("\n" + "=" * 50)
            print("Summary:")
            print("=" * 50)
            print(f"  Users created: {len(users)}")
            print(f"    - Active: {len([u for u in users if u.status == 'active'])}")
            print(f"    - Suspended: {len([u for u in users if u.status == 'suspended'])}")
            print(f"    - Banned: {len([u for u in users if u.status == 'banned'])}")
            print(f"    - Pending: {len([u for u in users if u.status == 'pending'])}")
            print(f"  Verification status:")
            print(f"    - Verified: {len([u for u in users if u.verification_status == 'verified'])}")
            print(f"    - Partial: {len([u for u in users if u.verification_status == 'partial'])}")
            print(f"    - Unverified: {len([u for u in users if u.verification_status == 'unverified'])}")
            print(f"  Profiles created: {len(profiles)}")
            print(f"    - Male: {len([p for p in profiles if p.gender == 'male'])}")
            print(f"    - Female: {len([p for p in profiles if p.gender == 'female'])}")
            print(f"    - Visible: {len([p for p in profiles if p.is_visible])}")
            print(f"  Verifications created: {len(verifications)}")
            print(f"    - Pending: {len([v for v in verifications if v.status == 'pending'])}")
            print(f"    - Processing: {len([v for v in verifications if v.status == 'processing'])}")
            print(f"    - Manual Review: {len([v for v in verifications if v.status == 'manual_review'])}")
            print(f"  Reports created: {len(reports)}")
            print(f"    - Pending: {len([r for r in reports if r.status == 'pending'])}")
            print(f"    - Reviewed: {len([r for r in reports if r.status == 'reviewed'])}")
            print(f"    - Dismissed: {len([r for r in reports if r.status == 'dismissed'])}")
            print(f"    - Action Taken: {len([r for r in reports if r.status == 'action_taken'])}")
            print("\nTest user login (male):")
            print("  Email: user1@test.nikoh.com")
            print("  Password: Test1234!")
            print("\nTest user login (female):")
            print("  Email: user2@test.nikoh.com")
            print("  Password: Test1234!")
            print("=" * 50)

        except Exception as e:
            print(f"\nError: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
