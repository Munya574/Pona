from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Enum, Float, Boolean, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()

# ── Association table for many-to-many: profile <-> sensitivity ────────────────
# Why a separate table? Allows one profile to have many sensitivities
# and querying which profiles have a specific sensitivity
user_sensitivities_table = Table(
    'user_sensitivities',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('profile_id', Integer, ForeignKey('sensitivity_profiles.id', ondelete='CASCADE'), nullable=False),
    Column('sensitivity_name', String(255), nullable=False),
    Column('severity_override', String(50), nullable=True),  # User can override severity
    Column('created_at', DateTime, default=datetime.utcnow),
)


class User(Base):
    """
    Represents a user account.

    Why separate from profiles?
    - User = identity (account, authentication, settings)
    - Profile = dietary restrictions (can have multiple)
    - Example: One user (John) manages profiles for himself + 2 kids
    """
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship: one user can have many profiles
    profiles = relationship('SensitivityProfile', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User {self.email}>"


class SensitivityProfile(Base):
    """
    A profile represents one person's dietary restrictions.

    Why profiles exist:
    - MVP: one user, one profile (their restrictions)
    - Future: parents manage profiles for multiple kids
    - Future: track dietary changes over time (phases)

    Think of it like Netflix profiles — one account, multiple viewers.
    """
    __tablename__ = 'sensitivity_profiles'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    profile_name = Column(String(255), default='My Profile')  # "Me", "Mom", "Son", etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='profiles')
    scans = relationship('Scan', back_populates='profile', cascade='all, delete-orphan')
    personal_triggers = relationship(
        'PersonalTrigger', back_populates='profile', cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Profile {self.profile_name} for user {self.user_id}>"

    def get_sensitivity_names(self, db) -> list:
        """
        Return this profile's sensitivity names.

        Note there is deliberately no `sensitivities` ORM relationship.
        user_sensitivities stores names as plain strings rather than rows in
        a `sensitivities` table, so there is no second entity to relate to —
        a relationship() here would have nothing valid to point at. We query
        the association table directly instead.
        """
        from sqlalchemy import select
        query = select(user_sensitivities_table.c.sensitivity_name).where(
            user_sensitivities_table.c.profile_id == self.id
        )
        return list(db.execute(query).scalars().all())


class PersonalTrigger(Base):
    """
    A food the user has told us THEY react to.

    Why this exists:

    For some conditions the trigger foods genuinely differ from person to
    person — reflux is the clearest case. Shipping a built-in list would
    mean asserting that everyone with reflux reacts to tomato and coffee,
    which is not supported and pushes people to cut out foods that are
    fine for them. So Pona ships no list for those conditions and watches
    for what each person actually reports instead.

    `condition` is optional context ("Acid reflux / GERD"), not a claim by
    Pona that the ingredient causes that condition. The user said it; we
    record it and look for it.
    """
    __tablename__ = 'personal_triggers'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('sensitivity_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    ingredient = Column(String(255), nullable=False)
    condition = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship('SensitivityProfile', back_populates='personal_triggers')

    def __repr__(self):
        return f"<PersonalTrigger {self.ingredient} ({self.condition})>"


class Scan(Base):
    """
    Represents one food scan (photo, OCR, or recipe URL).

    This is an audit trail that enables:
    - Debugging: what did the user scan, what verdict did they get?
    - Analytics: what foods do users scan most?
    - Future: pattern detection (did user get sick after this scan?)
    """
    __tablename__ = 'scans'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('sensitivity_profiles.id', ondelete='CASCADE'), nullable=False, index=True)

    # Input tracking
    input_type = Column(String(50), nullable=False)  # "photo", "ocr", "url"
    raw_ingredients = Column(JSON, nullable=True)  # Before normalization: ["milk", "sodium caseinate"]

    # Processing tracking
    normalized_ingredients = Column(JSON, nullable=True)  # After NLP: ["dairy", "dairy"]

    # Verdict
    verdict = Column(String(50), nullable=False)  # "safe", "caution", "unsafe"
    triggers = Column(JSON, nullable=True)  # List of { ingredient, sensitivity, explanation, severity }

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationship
    profile = relationship('SensitivityProfile', back_populates='scans')

    def __repr__(self):
        return f"<Scan {self.id}: {self.verdict} ({len(self.triggers or [])} triggers)>"


# ── Why this schema? ───────────────────────────────────────────────────────────
#
# NORMALIZATION (database design principle):
#
# BAD approach:
#   users table: id, email, sensitivities (comma-separated string), profile_name
#   → Hard to query: "which users are lactose intolerant?"
#   → Can't have multiple profiles per user
#
# GOOD approach (what we did):
#   users → sensitivity_profiles → user_sensitivities (join table)
#   → Can query: find all profiles with lactose intolerance
#   → Can add multiple profiles without data duplication
#   → Can scale to hundreds of sensitivities per profile
#
# RECRUITERS WILL ASK:
# "Why separate users and profiles?"
# Answer: "Normalization principle. Separates concerns: identity vs. preferences.
#          Enables multi-profile support without schema changes."
