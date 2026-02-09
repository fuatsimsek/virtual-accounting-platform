from flask import Blueprint

bp = Blueprint('helpdesk', __name__)

from . import routes
