# -*- coding: utf-8 -*-
import datetime
from http import HTTPStatus
import logging

from functools import wraps
from typing import Union

from flask import g, request
from flask_restful import Resource, Api
from flask_mail import Mail
from flask_jwt_extended import (
    get_jwt, get_jwt_identity, jwt_required
)
from flask_socketio import SocketIO
from marshmallow_sqlalchemy import ModelSchema


from vantage6.common import logger_name
from vantage6.server import db
from vantage6.server.permission import PermissionManager
from vantage6.server.resource.pagination import Page

log = logging.getLogger(logger_name(__name__))


class ServicesResources(Resource):
    """
    Flask resource base class.

    Adds functionality like mail, socket, permissions and the api itself.
    Also adds common helper functions.

    Attributes
    ----------
    socketio : SocketIO
        SocketIO instance
    mail : Mail
        Mail instance
    api : Api
        Api instance
    permissions : PermissionManager
        Instance of class that manages permissions
    config : dict
        Configuration dictionary
    """
    def __init__(self, socketio: SocketIO, mail: Mail, api: Api,
                 permissions: PermissionManager, config: dict):
        self.socketio = socketio
        self.mail = mail
        self.api = api
        self.permissions = permissions
        self.config = config

    @staticmethod
    def is_included(field) -> bool:
        """
        Check that a `field` is included in the request argument context.

        Parameters
        ----------
        field : str
            Name of the field to check

        Returns
        -------
        bool
            True if the field is included, False otherwise
        """
        return field in request.args.getlist('include')

    def dump(self, page: Page, schema: ModelSchema) -> dict:
        """
        Dump based on the request context (to paginate or not)

        Parameters
        ----------
        page : Page
            Page object to dump
        schema : ModelSchema
            Schema to use for dumping

        Returns
        -------
        dict
            Dumped page
        """
        if self.is_included('metadata'):
            return schema.meta_dump(page)
        else:
            return schema.default_dump(page)

    def response(self, page: Page, schema: ModelSchema):
        """
        Prepare a valid HTTP OK response from a page object

        Parameters
        ----------
        page : Page
            Page object to dump
        schema : ModelSchema
            Schema to use for dumping

        Returns
        -------
        tuple
            Tuple of (dumped page, HTTPStatus.OK, headers of the page)
        """
        return self.dump(page, schema), HTTPStatus.OK, page.headers

    @staticmethod
    def obtain_auth() -> Union[db.Authenticatable, dict]:
        """
        Read authenticatable object or dict from the flask global context.

        Returns
        -------
        Union[db.Authenticatable, dict]
            Authenticatable object or dict. Authenticatable object is either a
            user or node. Dict is for a container.
        """
        if g.user:
            return g.user
        if g.node:
            return g.node
        if g.container:
            return g.container

    @staticmethod
    def obtain_organization_id() -> int:
        """
        Obtain the organization id from the auth that is logged in.

        Returns
        -------
        int
            Organization id
        """
        if g.user:
            return g.user.organization.id
        elif g.node:
            return g.node.organization.id
        else:
            return g.container["organization_id"]

    @classmethod
    def obtain_auth_organization(cls) -> db.Organization:
        """
        Obtain the organization model from the auth that is logged in.

        Returns
        -------
        db.Organization
            Organization model
        """
        return db.Organization.get(cls.obtain_organization_id())


# ------------------------------------------------------------------------------
# Helper functions/decoraters ...
# ------------------------------------------------------------------------------
def only_for(types: tuple[str] = ('user', 'node', 'container')):
    """
    JWT endpoint protection decorator

    Parameters
    ----------
    types : list[str]
        List of types that are allowed to access the endpoint. Possible types
        are 'user', 'node' and 'container'.

    Returns
    -------
    function
        Decorator function that can be used to protect endpoints
    """
    def protection_decorator(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):

            # decode JWT-token
            identity = get_jwt_identity()
            claims = get_jwt()

            # check that identity has access to endpoint
            g.type = claims["client_type"]
            # log.debug(f"Endpoint accessed as {g.type}")

            if g.type not in types:
                # FIXME BvB 23-10-19: user gets a 500 error, would be better to
                # get an error message with 400 code
                msg = f"{g.type}s are not allowed to access {request.url} " \
                      f"({request.method})"
                log.warning(msg)
                raise Exception(msg)

            # do some specific stuff per identity
            g.user = g.container = g.node = None

            if g.type == 'user':
                user = get_and_update_authenticatable_info(identity)
                g.user = user
                assert g.user.type == g.type
                log.debug(
                    f"Received request from user {user.username} ({user.id})")

            elif g.type == 'node':
                node = get_and_update_authenticatable_info(identity)
                g.node = node
                assert g.node.type == g.type
                log.debug(
                    f"Received request from node {node.name} ({node.id})")

            elif g.type == 'container':
                g.container = identity
                log.debug(
                    "Received request from container with node id "
                    f"{identity['node_id']} and task id {identity['task_id']}")

            else:
                raise Exception(f"Unknown entity: {g.type}")

            return fn(*args, **kwargs)
        return jwt_required()(decorator)
    return protection_decorator


def get_and_update_authenticatable_info(auth_id: int) -> db.Authenticatable:
    """
    Get user or node from ID and update last time seen online.

    Parameters
    ----------
    auth_id : int
        ID of the user or node

    Returns
    -------
    db.Authenticatable
        User or node database model
    """
    auth = db.Authenticatable.get(auth_id)
    auth.last_seen = datetime.datetime.utcnow()
    auth.save()
    return auth


# create alias decorators
with_user_or_node = only_for(("user", "node",))
with_user = only_for(("user",))
with_node = only_for(("node",))
with_container = only_for(("container",))


def parse_datetime(dt: str = None, default: datetime = None) -> datetime:
    """
    Utility function to parse a datetime string.

    Parameters
    ----------
    dt : str
        Datetime string
    default : datetime
        Default datetime to return if `dt` is None

    Returns
    -------
    datetime
        Datetime object
    """
    if dt:
        return datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%f')
    return default
