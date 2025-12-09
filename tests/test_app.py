"""
Tests básicos para la aplicación Flask
"""
import pytest
from app import create_app, db
from app.models import Docente, Carrera, Estudiante


@pytest.fixture
def app():
    """Crea una instancia de la aplicación para testing"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente de prueba para hacer requests"""
    return app.test_client()


@pytest.fixture
def admin_user(app):
    """Crea un usuario administrador de prueba"""
    with app.app_context():
        admin = Docente(
            email='admin@test.com',
            password_hash='test_hash',
            nombre='Admin Test',
            rol='administrador'
        )
        db.session.add(admin)
        db.session.commit()
        return admin


@pytest.fixture
def docente_user(app):
    """Crea un usuario docente de prueba"""
    with app.app_context():
        carrera = Carrera(nombre='Ingeniería en Sistemas', clave='IS')
        db.session.add(carrera)
        db.session.commit()
        
        docente = Docente(
            email='docente@test.com',
            password_hash='test_hash',
            nombre='Docente Test',
            rol='docente',
            carrera_id=carrera.id
        )
        db.session.add(docente)
        db.session.commit()
        return docente


class TestAppInitialization:
    """Tests para verificar la inicialización de la aplicación"""
    
    def test_app_creation(self, app):
        """Verifica que la aplicación se crea correctamente"""
        assert app is not None
        assert app.config['TESTING'] is True
    
    def test_database_creation(self, app):
        """Verifica que las tablas se crean correctamente"""
        with app.app_context():
            from app.models import Docente, Carrera, Estudiante
            assert Docente is not None
            assert Carrera is not None
            assert Estudiante is not None


class TestAuthentication:
    """Tests para las rutas de autenticación"""
    
    def test_login_page_loads(self, client):
        """Verifica que la página de login carga correctamente"""
        response = client.get('/auth/login')
        assert response.status_code == 200
    
    def test_register_page_loads(self, client):
        """Verifica que la página de registro carga correctamente"""
        response = client.get('/auth/register')
        assert response.status_code == 200
    
    def test_login_redirects_when_not_authenticated(self, client):
        """Verifica que las rutas protegidas redirigen al login"""
        response = client.get('/')
        assert response.status_code == 302  # Redirect
        assert '/auth/login' in response.location


class TestModels:
    """Tests para los modelos de la base de datos"""
    
    def test_docente_creation(self, app, admin_user):
        """Verifica la creación de un docente"""
        with app.app_context():
            docente = Docente.query.filter_by(email='admin@test.com').first()
            assert docente is not None
            assert docente.email == 'admin@test.com'
            assert docente.rol == 'administrador'
    
    def test_docente_is_admin(self, app, admin_user):
        """Verifica el método is_admin()"""
        with app.app_context():
            admin = Docente.query.filter_by(email='admin@test.com').first()
            assert admin.is_admin() is True
    
    def test_carrera_creation(self, app):
        """Verifica la creación de una carrera"""
        with app.app_context():
            carrera = Carrera(nombre='Ingeniería Industrial', clave='II')
            db.session.add(carrera)
            db.session.commit()
            
            carrera_db = Carrera.query.filter_by(nombre='Ingeniería Industrial').first()
            assert carrera_db is not None
            assert carrera_db.clave == 'II'


class TestRoutes:
    """Tests para las rutas principales"""
    
    def test_index_requires_login(self, client):
        """Verifica que el index requiere autenticación"""
        response = client.get('/')
        assert response.status_code == 302  # Redirect to login
    
    def test_data_routes_require_login(self, client):
        """Verifica que las rutas de datos requieren autenticación"""
        response = client.get('/data/estudiantes')
        assert response.status_code == 302  # Redirect to login

