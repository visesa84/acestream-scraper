from flask_restx import Namespace, Resource, fields
from flask import request, current_app
from app.extensions import db
from app.models import User
import logging

logger = logging.getLogger(__name__)

api = Namespace('users', description='User management and authentication')

user_input_model = api.model('UserInput', {
    'username': fields.String(required=True, description='Username for the account'),
    'password': fields.String(required=True, description='Password for the account'),
    'is_admin': fields.Boolean(required=False, default=False, description='Is administrator account')
})

user_password_model = api.model('UserPassword', {
    'password': fields.String(required=True, description='New password for the account')
})

user_model = api.model('User', {
    'id': fields.Integer(description='Unique identifier for the user'),
    'username': fields.String(description='Username'),
    'is_admin': fields.Boolean(description='Is admin status'),
    'created_at': fields.DateTime(description='Creation timestamp')
})

@api.route('/')
class UserList(Resource):
    @api.doc('list_users')
    @api.marshal_list_with(user_model)
    def get(self):
        """Obtener la lista de todos los usuarios registrados."""
        try:
            users = User.query.all()
            return users
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            api.abort(500, str(e))
    
    @api.doc('create_user')
    @api.expect(user_input_model)
    @api.response(201, 'User created successfully')
    @api.response(400, 'Invalid input or user already exists')
    def post(self):
        """Crear un nuevo usuario."""
        data = request.json or {}
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        is_admin = bool(data.get('is_admin', False))
        
        if not username or not password:
            return {'error': 'Username and password are required'}, 400
        
        try:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return {'error': 'User already exists'}, 400
            
            new_user = User(username=username, is_admin=is_admin)
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            logger.info(f"User '{username}' created successfully (Admin: {is_admin}).")
            return {
                'message': 'User created successfully',
                'id': new_user.id,
                'username': new_user.username,
                'is_admin': new_user.is_admin
            }, 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating user: {e}", exc_info=True)
            api.abort(500, str(e))

@api.route('/<int:id>')
@api.param('id', 'The user ID')
class UserItem(Resource):
    @api.doc('change_password')
    @api.expect(user_password_model)
    @api.response(200, 'Password updated successfully')
    @api.response(404, 'User not found')
    @api.response(400, 'Invalid password')
    def put(self, id):
        """Actualizar la contraseña de un usuario por su ID."""
        data = request.json or {}
        password = data.get('password', '').strip()
        
        if not password:
            return {'error': 'Password is required'}, 400
            
        try:
            user_obj = User.query.get(id)
            if not user_obj:
                api.abort(404, 'User not found')
                
            user_obj.set_password(password)
            db.session.commit()
            
            logger.info(f"Successfully updated password for user ID: {id}")
            return {'message': 'Password updated successfully'}, 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating password: {e}", exc_info=True)
            api.abort(500, str(e))

    @api.doc('delete_user')
    @api.response(204, 'User deleted')
    @api.response(404, 'User not found')
    @api.response(400, 'Cannot delete the last remaining user')
    def delete(self, id):
        """Eliminar un usuario por su ID (evitando borrar el último admin)."""
        try:
            user_obj = User.query.get(id)
            if not user_obj:
                api.abort(404, 'User not found')
            
            if User.query.count() <= 1:
                return {'error': 'Cannot delete the last remaining user in the system'}, 400
            
            db.session.delete(user_obj)
            db.session.commit()
            
            logger.info(f"Successfully deleted user ID: {id}")
            return '', 204
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting user: {e}", exc_info=True)
            api.abort(500, str(e))