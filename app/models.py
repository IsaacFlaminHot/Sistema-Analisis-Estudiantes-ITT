from datetime import datetime
from flask_login import UserMixin
from . import db, login_manager
from sqlalchemy import UniqueConstraint


class Docente(UserMixin, db.Model):
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(120), unique=True, nullable=False)
	password_hash = db.Column(db.String(255), nullable=False)
	nombre = db.Column(db.String(120), nullable=False)
	rol = db.Column(db.String(20), nullable=False, default="docente")  # "administrador" o "docente"
	carrera_id = db.Column(db.Integer, db.ForeignKey("carrera.id"), nullable=True)  # Solo para docentes
	creado_en = db.Column(db.DateTime, default=datetime.utcnow)
	
	# Relación con Carrera
	carrera_rel = db.relationship("Carrera", backref="docentes", lazy=True)
	
	def is_admin(self):
		"""Verifica si el docente es administrador"""
		return self.rol == "administrador"


@login_manager.user_loader
def load_user(user_id: str):
	return Docente.query.get(int(user_id))


class Carrera(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	nombre = db.Column(db.String(120), unique=True, nullable=False)
	clave = db.Column(db.String(20), unique=True, nullable=True)
	creado_en = db.Column(db.DateTime, default=datetime.utcnow)

	materias = db.relationship("Materia", backref="carrera_rel", lazy=True)


class Estudiante(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	matricula = db.Column(db.String(32), unique=True, nullable=False)
	apellido_paterno = db.Column(db.String(64), nullable=False)
	apellido_materno = db.Column(db.String(64), nullable=False)
	nombres = db.Column(db.String(80), nullable=False)
	genero = db.Column(db.String(20), nullable=True)
	modalidad = db.Column(db.String(20), nullable=True)
	carrera = db.Column(db.String(120), nullable=False)
	semestre = db.Column(db.Integer, nullable=False)
	estado = db.Column(db.String(20), nullable=False, default="Activo")  # Activo, Desertor, Egresado
	creado_en = db.Column(db.DateTime, default=datetime.utcnow)

	calificaciones = db.relationship("Calificacion", backref="estudiante", lazy=True, cascade="all, delete-orphan")
	factores = db.relationship("FactorRiesgo", backref="estudiante", lazy=True, cascade="all, delete-orphan")


class Materia(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	nombre = db.Column(db.String(120), nullable=False)
	semestre = db.Column(db.Integer, nullable=False)
	carrera_id = db.Column(db.Integer, db.ForeignKey("carrera.id"), nullable=True)

	calificaciones = db.relationship("Calificacion", backref="materia", lazy=True, cascade="all, delete-orphan")
	
	__table_args__ = (
		UniqueConstraint("nombre", "carrera_id", name="uq_materia_nombre_carrera"),
	)


class Calificacion(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	estudiante_id = db.Column(db.Integer, db.ForeignKey("estudiante.id"), nullable=False)
	materia_id = db.Column(db.Integer, db.ForeignKey("materia.id"), nullable=False)
	nota = db.Column(db.Float, nullable=False)  # 0-100
	asistencia = db.Column(db.Float, nullable=False)  # 0-100
	periodo = db.Column(db.String(20), nullable=False)  # p.e. 2025-1

	__table_args__ = (
		UniqueConstraint("estudiante_id", "materia_id", "periodo", name="uq_cal_est_mat_per"),
	)


class FactorRiesgo(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	estudiante_id = db.Column(db.Integer, db.ForeignKey("estudiante.id"), nullable=False)
	tipo = db.Column(db.String(40), nullable=False)  # Academico, Psicosocial, Economico, Institucional, Contextual
	valor = db.Column(db.String(120), nullable=False)  # etiqueta/descripcion
	periodo = db.Column(db.String(20), nullable=False)


class Auditoria(db.Model):
	"""Registro de todas las operaciones realizadas en el sistema"""
	id = db.Column(db.Integer, primary_key=True)
	usuario_id = db.Column(db.Integer, db.ForeignKey("docente.id"), nullable=True)
	usuario_nombre = db.Column(db.String(120), nullable=True)  # Cache del nombre por si se elimina el usuario
	accion = db.Column(db.String(20), nullable=False)  # CREATE, UPDATE, DELETE
	entidad = db.Column(db.String(50), nullable=False)  # Estudiante, Materia, Carrera, Calificacion, FactorRiesgo
	entidad_id = db.Column(db.Integer, nullable=True)  # ID del registro afectado
	descripcion = db.Column(db.Text, nullable=True)  # Descripción detallada del cambio
	datos_anteriores = db.Column(db.Text, nullable=True)  # JSON con datos antes del cambio (para UPDATE)
	datos_nuevos = db.Column(db.Text, nullable=True)  # JSON con datos después del cambio (para CREATE/UPDATE)
	fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	
	# Relación opcional con Docente
	usuario = db.relationship("Docente", backref="auditorias", lazy=True)
