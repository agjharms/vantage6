from __future__ import annotations
import bcrypt
import re
import datetime as dt

from typing import Tuple, Union
from sqlalchemy import Column, String, Integer, ForeignKey, exists, DateTime
from sqlalchemy.orm import relationship, validates

from vantage6.server.model.base import DatabaseSessionManager
from vantage6.server.model.authenticatable import Authenticatable
from vantage6.server.model.rule import Operation, Rule, Scope


class User(Authenticatable):
    """
    Table to keep track of Users (persons) that can access the system.

    Users always belong to an organization and can have certain
    rights within an organization.

    Attributes
    ----------
    username : str
        Username of the user
    password : str
        Password of the user
    firstname : str
        First name of the user
    lastname : str
        Last name of the user
    email : str
        Email address of the user
    organization_id : int
        Foreign key to the organization to which the user belongs
    failed_login_attempts : int
        Number of failed login attempts
    last_login_attempt : datetime.datetime
        Date and time of the last login attempt
    otp_secret : str
        Secret key for one time passwords
    organization : :class:`~.model.organization.Organization`
        Organization to which the user belongs
    roles : list[:class:`~.model.role.Role`]
        Roles that the user has
    rules : list[:class:`~.model.rule.Rule`]
        Rules that the user has
    created_tasks : list[:class:`~.model.task.Task`]
        Tasks that the user has created
    """
    _hidden_attributes = ['password']

    # overwrite id with linked id to the authenticatable
    id = Column(Integer, ForeignKey('authenticatable.id'), primary_key=True)
    __mapper_args__ = {
        'polymorphic_identity': 'user',
    }

    # fields
    username = Column(String, unique=True)
    password = Column(String)
    firstname = Column(String)
    lastname = Column(String)
    email = Column(String, unique=True)
    organization_id = Column(Integer, ForeignKey("organization.id"))
    failed_login_attempts = Column(Integer, default=0)
    last_login_attempt = Column(DateTime)
    otp_secret = Column(String(32))

    # relationships
    organization = relationship("Organization", back_populates="users")
    roles = relationship("Role", back_populates="users",
                         secondary="Permission")
    rules = relationship("Rule", back_populates="users",
                         secondary="UserPermission")
    created_tasks = relationship("Task", back_populates="init_user")

    def __repr__(self) -> str:
        """
        String representation of the user.

        Returns
        -------
        str
            String representation of the user
        """
        organization = self.organization.name if self.organization else "None"
        return (
            f"<User "
            f"id={self.id}, username='{self.username}', roles='{self.roles}', "
            f"organization='{organization}'"
            f">"
        )

    @validates("password")
    def _validate_password(self, key: str, password: str) -> str:
        """
        Validate the password of the user by hashing it, as it is also hashed
        in the database.

        Parameters
        ----------
        key: str
            Name of the attribute (in this case 'password')
        password: str
            Password of the user

        Returns
        -------
        str
            Hashed password
        """
        return self.hash(password)

    def set_password(self, pw: str) -> Union[str, None]:
        """
        Set the password of the current user. This function doesn't save the
        new password to the database

        Parameters
        ----------
        pw: str
            The new password

        Returns
        -------
        str | None
            If the new password fails to pass the checks, a message is
            returned. Else, none is returned
        """
        if len(pw) < 8:
            return (
                "Password too short: use at least 8 characters with mixed "
                "lowercase, uppercase, numbers and special characters"
            )
        elif len(pw) > 128:
            # because long passwords can be used for DoS attacks (long pw
            # hashing consumes a lot of resources)
            return "Password too long: use at most 128 characters"
        elif re.search('[0-9]', pw) is None:
            return "Password should contain at least one number"
        elif re.search('[A-Z]', pw) is None:
            return "Password should contain at least one uppercase letter"
        elif re.search('[a-z]', pw) is None:
            return "Password should contain at least one lowercase letter"
        elif pw.isalnum():
            return "Password should contain at least one special character"

        self.password = pw
        self.save()

    def check_password(self, pw: str) -> bool:
        """
        Check if the password is correct

        Parameters
        ----------
        pw: str
            Password to check

        Returns
        -------
        bool
            Whether or not the password is correct
        """
        if self.password is not None:
            expected_hash = self.password.encode('utf8')
            return bcrypt.checkpw(pw.encode('utf8'), expected_hash)
        return False

    def is_blocked(self, max_failed_attempts: int,
                   inactivation_in_minutes: int) -> Tuple[bool, str | None]:
        """
        Check if user can login or if they are temporarily blocked because they
        entered a wrong password too often

        Parameters
        ----------
        max_failed_attempts: int
            Maximum number of attempts to login before temporary deactivation
        inactivation_minutes: int
            How many minutes an account is deactivated

        Returns
        -------
        bool
            Whether or not user is blocked temporarily
        str | None
            Message if user is blocked, else None
        """
        td_max_blocked = dt.timedelta(minutes=inactivation_in_minutes)
        td_last_login = dt.datetime.now() - self.last_login_attempt \
            if self.last_login_attempt else None
        has_max_attempts = (
            self.failed_login_attempts >= max_failed_attempts
            if self.failed_login_attempts else False
        )
        if has_max_attempts and td_last_login < td_max_blocked:
            minutes_remaining = \
                (td_max_blocked - td_last_login).seconds // 60 + 1
            return True, minutes_remaining
        else:
            return False, None

    @classmethod
    def get_by_username(cls, username: str) -> User:
        """
        Get a user by their username

        Parameters
        ----------
        username: str
            Username of the user

        Returns
        -------
        User
            User with the given username

        Raises
        ------
        NoResultFound
            If no user with the given username exists
        """
        session = DatabaseSessionManager.get_session()
        result = session.query(cls).filter_by(username=username).one()
        session.commit()
        return result

    @classmethod
    def get_by_email(cls, email: str) -> User:
        """
        Get a user by their email

        Parameters
        ----------
        email: str
            Email of the user

        Returns
        -------
        User
            User with the given email

        Raises
        ------
        NoResultFound
            If no user with the given email exists
        """
        session = DatabaseSessionManager.get_session()
        result = session.query(cls).filter_by(email=email).one()
        session.commit()
        return result

    @classmethod
    def username_exists(cls, username: str) -> bool:
        """
        Checks if user with certain username exists

        Parameters
        ----------
        username: str
            Username to check

        Returns
        -------
        bool
            Whether or not user with given username exists
        """
        session = DatabaseSessionManager.get_session()
        result = session.query(exists().where(cls.username == username))\
            .scalar()
        session.commit()
        return result

    @classmethod
    def exists(cls, field: str, value: str) -> bool:
        """
        Checks if user with certain key-value exists

        Parameters
        ----------
        field: str
            Name of the attribute to check
        value: str
            Value of the attribute to check

        Returns
        -------
        bool
            Whether or not user with given key-value exists
        """
        session = DatabaseSessionManager.get_session()
        result = session.query(exists().where(getattr(cls, field) == value))\
            .scalar()
        session.commit()
        return result

    def can(self, resource: str, scope: Scope, operation: Operation) -> bool:
        """
        Check if user is allowed to execute a certain action

        Parameters
        ---------
        resource: str
            The resource type on which the action is to be performed
        scope: Scope
            The scope within which the user wants to perform an action
        operation: Operation
            The operation a user wants to execute

        Returns
        -------
        bool
            Whether or not user is allowed to execute the requested operation
            on the resource
        """
        rule = Rule.get_by_(resource, scope, operation)
        return rule in self.rules or \
            any(rule in role.rules for role in self.roles)
