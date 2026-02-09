from flask import Blueprint

bp = Blueprint('blog', __name__)

from . import routes
