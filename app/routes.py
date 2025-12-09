from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, jsonify, Response
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import json

from . import db
from .models import Docente, Estudiante, Materia, Calificacion, FactorRiesgo, Carrera, Auditoria

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
main_bp = Blueprint("main", __name__)
data_bp = Blueprint("data", __name__, url_prefix="/data")


def registrar_auditoria(accion, entidad, entidad_id=None, descripcion=None, datos_anteriores=None, datos_nuevos=None):
	"""Función helper para registrar cambios en el sistema de auditoría"""
	try:
		usuario_id = current_user.id if current_user.is_authenticated else None
		usuario_nombre = current_user.nombre if current_user.is_authenticated else "Sistema"
		
		# Convertir diccionarios a JSON si es necesario
		if isinstance(datos_anteriores, dict):
			datos_anteriores = json.dumps(datos_anteriores, ensure_ascii=False, default=str)
		if isinstance(datos_nuevos, dict):
			datos_nuevos = json.dumps(datos_nuevos, ensure_ascii=False, default=str)
		
		audit = Auditoria(
			usuario_id=usuario_id,
			usuario_nombre=usuario_nombre,
			accion=accion,
			entidad=entidad,
			entidad_id=entidad_id,
			descripcion=descripcion,
			datos_anteriores=datos_anteriores,
			datos_nuevos=datos_nuevos
		)
		db.session.add(audit)
		db.session.commit()
	except Exception as e:
		# Si falla la auditoría, no debe romper la operación principal
		db.session.rollback()
		print(f"Error al registrar auditoría: {e}")


def obtener_carrera_docente():
	"""Obtiene la carrera del docente actual. Retorna None si es administrador o no tiene carrera."""
	if not current_user.is_authenticated:
		return None
	if current_user.is_admin():
		return None  # Los administradores no tienen restricción de carrera
	if current_user.carrera_rel:
		return current_user.carrera_rel.nombre
	return None


def aplicar_filtro_carrera(query, modelo):
	"""Aplica filtro de carrera a una consulta si el usuario es docente"""
	if current_user.is_authenticated and not current_user.is_admin():
		carrera_nombre = obtener_carrera_docente()
		if carrera_nombre:
			# Si el modelo tiene campo carrera (como Estudiante)
			if hasattr(modelo, 'carrera'):
				query = query.filter(modelo.carrera == carrera_nombre)
			# Si el modelo tiene carrera_id (como Materia)
			elif hasattr(modelo, 'carrera_id'):
				carrera_obj = Carrera.query.filter_by(nombre=carrera_nombre).first()
				if carrera_obj:
					query = query.filter(modelo.carrera_id == carrera_obj.id)
	return query


def apply_dark_theme(fig):
	"""Aplica tema oscuro a un gráfico de Plotly"""
	# Obtener layout actual
	layout = fig.layout
	
	# Aplicar tema oscuro base
	fig.update_layout(
		plot_bgcolor='#000000',
		paper_bgcolor='#000000',
		font=dict(color='#f5f5f7', family='PPNeueMachina, sans-serif'),
		title_font=dict(color='#f5f5f7', family='PPNeueMachina, sans-serif'),
		xaxis=dict(
			gridcolor='rgba(255, 255, 255, 0.1)',
			linecolor='rgba(255, 255, 255, 0.2)',
			zerolinecolor='rgba(255, 255, 255, 0.1)',
			tickfont=dict(color='#86868b')
		),
		yaxis=dict(
			gridcolor='rgba(255, 255, 255, 0.1)',
			linecolor='rgba(255, 255, 255, 0.2)',
			zerolinecolor='rgba(255, 255, 255, 0.1)',
			tickfont=dict(color='#86868b')
		),
		legend=dict(
			bgcolor='rgba(0, 0, 0, 0.8)',
			bordercolor='rgba(255, 255, 255, 0.1)',
			font=dict(color='#f5f5f7')
		)
	)
	
	# Si hay ejes secundarios (yaxis2, xaxis2, etc.), aplicarles también el tema
	for axis_name in ['xaxis2', 'xaxis3', 'xaxis4', 'yaxis2', 'yaxis3', 'yaxis4']:
		if hasattr(layout, axis_name) and getattr(layout, axis_name) is not None:
			axis_config = getattr(layout, axis_name)
			if isinstance(axis_config, dict):
				fig.update_layout({
					axis_name: dict(
						gridcolor='rgba(255, 255, 255, 0.1)',
						linecolor='rgba(255, 255, 255, 0.2)',
						zerolinecolor='rgba(255, 255, 255, 0.1)',
						tickfont=dict(color='#86868b'),
						title_font=dict(color='#f5f5f7')
					)
				})
	
	return fig


@main_bp.route("/favicon.ico")
def favicon():
	# Respuesta vacía para que el navegador no dispare redirección protegida y duplica mensajes
	return Response(status=204)


# ---------- Carreras ----------
@data_bp.route("/carreras")
@login_required
def carreras_list():
	# Solo administradores pueden ver y gestionar carreras
	if not current_user.is_admin():
		flash("No tienes permiso para acceder a esta sección", "warning")
		return redirect(url_for("main.index"))
	carreras = Carrera.query.order_by(Carrera.nombre).all()
	return render_template("carreras_list.html", carreras=carreras)


@data_bp.route("/carreras/create", methods=["POST"])
@login_required
def carreras_create():
	# Solo administradores pueden crear carreras
	if not current_user.is_admin():
		flash("No tienes permiso para realizar esta acción", "warning")
		return redirect(url_for("main.index"))
	nombre = request.form.get("nombre", "").strip()
	clave = request.form.get("clave", "").strip() or None
	if not nombre:
		flash("Nombre requerido", "warning")
		return redirect(url_for("data.carreras_list"))
	if Carrera.query.filter((Carrera.nombre == nombre) | ((Carrera.clave == clave) if clave else False)).first():
		flash("Carrera ya existente (por nombre o clave)", "danger")
		return redirect(url_for("data.carreras_list"))
	c = Carrera(nombre=nombre, clave=clave)
	db.session.add(c)
	db.session.commit()
	registrar_auditoria(
		accion="CREATE",
		entidad="Carrera",
		entidad_id=c.id,
		descripcion=f"Carrera creada: {nombre}" + (f" (Clave: {clave})" if clave else ""),
		datos_nuevos={"nombre": nombre, "clave": clave}
	)
	flash("Carrera creada", "success")
	return redirect(url_for("data.carreras_list"))


@data_bp.route("/carreras/<int:car_id>/edit", methods=["POST"])
@login_required
def carreras_edit(car_id: int):
	# Solo administradores pueden editar carreras
	if not current_user.is_admin():
		flash("No tienes permiso para realizar esta acción", "warning")
		return redirect(url_for("main.index"))
	c = Carrera.query.get_or_404(car_id)
	datos_anteriores = {"nombre": c.nombre, "clave": c.clave}
	new_nombre = request.form.get("nombre", c.nombre).strip()
	new_clave = request.form.get("clave", c.clave or "").strip() or None
	# Validar que no choque con otra carrera
	dup = Carrera.query.filter(
		(Carrera.id != c.id) & ((Carrera.nombre == new_nombre) | ((Carrera.clave == new_clave) if new_clave else False))
	).first()
	if dup:
		flash("Ya existe otra carrera con ese nombre/clave", "warning")
		return redirect(url_for("data.carreras_list"))
	c.nombre = new_nombre
	c.clave = new_clave
	db.session.commit()
	registrar_auditoria(
		accion="UPDATE",
		entidad="Carrera",
		entidad_id=c.id,
		descripcion=f"Carrera actualizada: {new_nombre}" + (f" (Clave: {new_clave})" if new_clave else ""),
		datos_anteriores=datos_anteriores,
		datos_nuevos={"nombre": new_nombre, "clave": new_clave}
	)
	flash("Carrera actualizada", "success")
	return redirect(url_for("data.carreras_list"))


@data_bp.route("/carreras/<int:car_id>/delete", methods=["POST"])
@login_required
def carreras_delete(car_id: int):
	c = Carrera.query.get_or_404(car_id)
	nombre_carrera = c.nombre
	datos_eliminados = {"nombre": c.nombre, "clave": c.clave}
	db.session.delete(c)
	db.session.commit()
	registrar_auditoria(
		accion="DELETE",
		entidad="Carrera",
		entidad_id=car_id,
		descripcion=f"Carrera eliminada: {nombre_carrera}",
		datos_anteriores=datos_eliminados
	)
	flash("Carrera eliminada", "success")
	return redirect(url_for("data.carreras_list"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
	if request.method == "POST":
		email = request.form.get("email", "").strip().lower()
		nombre = request.form.get("nombre", "").strip()
		password = request.form.get("password", "")
		rol = request.form.get("rol", "docente").strip()
		carrera_id = request.form.get("carrera_id", "").strip() or None
		
		if not (email and nombre and password):
			flash("Todos los campos son obligatorios", "warning")
			return redirect(url_for("auth.register"))
		
		# Validar que si es docente, debe tener carrera
		if rol == "docente" and not carrera_id:
			flash("Los docentes deben seleccionar una carrera", "warning")
			return redirect(url_for("auth.register"))
		
		# Validar que la carrera existe si se proporciona
		if carrera_id:
			carrera = Carrera.query.get(int(carrera_id))
			if not carrera:
				flash("Carrera no válida", "danger")
				return redirect(url_for("auth.register"))
		
		if Docente.query.filter_by(email=email).first():
			flash("El correo ya está registrado", "danger")
			return redirect(url_for("auth.register"))
		
		doc = Docente(
			email=email,
			nombre=nombre,
			password_hash=generate_password_hash(password),
			rol=rol,
			carrera_id=int(carrera_id) if carrera_id else None
		)
		db.session.add(doc)
		db.session.commit()
		flash("Cuenta creada, ya puedes iniciar sesión", "success")
		return redirect(url_for("auth.login"))
	
	carreras = Carrera.query.order_by(Carrera.nombre).all()
	return render_template("register.html", carreras=carreras)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
	if request.method == "POST":
		email = request.form.get("email", "").strip().lower()
		password = request.form.get("password", "")
		doc = Docente.query.filter_by(email=email).first()
		if doc and check_password_hash(doc.password_hash, password):
			login_user(doc)
			return redirect(url_for("main.index"))
		flash("Credenciales inválidas", "danger")
	return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
	logout_user()
	return redirect(url_for("auth.login"))


@main_bp.route("/")
@login_required
def index():
	# Construir consultas base
	query_estudiantes = Estudiante.query
	query_calificaciones = Calificacion.query
	
	# Aplicar filtro de carrera si es docente
	if not current_user.is_admin():
		carrera_nombre = obtener_carrera_docente()
		if carrera_nombre:
			query_estudiantes = query_estudiantes.filter(Estudiante.carrera == carrera_nombre)
			# Filtrar calificaciones por estudiantes de la carrera
			estudiantes_ids = [e.id for e in query_estudiantes.all()]
			if estudiantes_ids:
				query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id.in_(estudiantes_ids))
			else:
				query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id == -1)
	
	# Indicadores básicos
	total = query_estudiantes.count()
	reprobados = query_calificaciones.filter(Calificacion.nota < 70).count()
	# desertores: estado == "Desertor"
	desertores = query_estudiantes.filter_by(estado="Desertor").count()
	reprobacion_prom = 0.0
	total_calificaciones = query_calificaciones.count()
	if total:
		reprobacion_prom = round(100 * reprobados / max(total_calificaciones, 1), 2)
	desercion_est = round(100 * desertores / max(total, 1), 2)

	# Obtener semestres únicos de estudiantes desertores para el filtro
	semestres_query = db.session.query(Estudiante.semestre).filter(
		Estudiante.estado == "Desertor"
	)
	if not current_user.is_admin():
		carrera_nombre = obtener_carrera_docente()
		if carrera_nombre:
			semestres_query = semestres_query.filter(Estudiante.carrera == carrera_nombre)
	semestres_disponibles = semestres_query.distinct().order_by(Estudiante.semestre).all()
	semestres = [s[0] for s in semestres_disponibles]

	# histograma simple de notas
	notas = [c.nota for c in query_calificaciones.all()]
	if notas:
		fig = px.histogram(notas, nbins=10, title="Distribución de calificaciones")
		fig.update_traces(marker_color='#0071e3')
	else:
		fig = go.Figure()
	fig = apply_dark_theme(fig)
	graph_json = fig.to_json()
	
	return render_template(
		"index.html",
		indicadores={
			"total": total,
			"reprobacion_prom": reprobacion_prom,
			"desercion_est": desercion_est,
		},
		graph_json=graph_json,
		semestres=semestres,
	)


# -------- CRUD Estudiantes --------
@data_bp.route("/estudiantes")
@login_required
def estudiantes_list():
	# Filtrar carreras según el rol del usuario
	if current_user.is_admin():
		carreras = Carrera.query.order_by(Carrera.nombre).all()
	else:
		# Docentes solo ven su carrera
		if current_user.carrera_rel:
			carreras = [current_user.carrera_rel]
		else:
			carreras = []
	
	# Filtrar materias según el rol del usuario
	if current_user.is_admin():
		materias = Materia.query.order_by(Materia.nombre).all()
	else:
		# Docentes solo ven materias de su carrera
		carrera_nombre = obtener_carrera_docente()
		if carrera_nombre:
			carrera_obj = Carrera.query.filter_by(nombre=carrera_nombre).first()
			if carrera_obj:
				materias = Materia.query.filter(
					(Materia.carrera_id == carrera_obj.id) | (Materia.carrera_id == None)
				).order_by(Materia.nombre).all()
			else:
				materias = []
		else:
			materias = []
	
	# Crear diccionario de materia_id -> carrera_id para el frontend
	materia_carrera_map = {}
	for m in materias:
		materia_carrera_map[m.id] = m.carrera_id
	
	# Obtener filtros de la URL
	carrera_id = request.args.get("carrera_id", "").strip()
	materia_id = request.args.get("materia_id", "").strip()
	
	# Construir consulta base
	query = Estudiante.query
	
	# Aplicar filtro automático por carrera si es docente
	query = aplicar_filtro_carrera(query, Estudiante)
	
	# Aplicar filtro por carrera (si se especifica en la URL)
	if carrera_id:
		carrera = Carrera.query.get(int(carrera_id))
		if carrera:
			# Si es docente, verificar que la carrera sea la suya
			if not current_user.is_admin():
				carrera_docente = obtener_carrera_docente()
				if carrera.nombre != carrera_docente:
					flash("No tienes permiso para ver esa carrera", "warning")
					return redirect(url_for("data.estudiantes_list"))
			query = query.filter(Estudiante.carrera == carrera.nombre)
	
	# Aplicar filtro por materia (después de carrera)
	if materia_id:
		materia = Materia.query.get(int(materia_id))
		if materia:
			# Si es docente, verificar que la materia sea de su carrera
			if not current_user.is_admin() and materia.carrera_id:
				carrera_docente = obtener_carrera_docente()
				carrera_obj = Carrera.query.filter_by(nombre=carrera_docente).first()
				if carrera_obj and materia.carrera_id != carrera_obj.id:
					flash("No tienes permiso para ver esa materia", "warning")
					return redirect(url_for("data.estudiantes_list"))
			
			# Obtener IDs de estudiantes que tienen calificaciones en esta materia
			estudiantes_ids = db.session.query(Calificacion.estudiante_id).filter(
				Calificacion.materia_id == materia.id
			).distinct().all()
			estudiantes_ids = [eid[0] for eid in estudiantes_ids]
			if estudiantes_ids:
				query = query.filter(Estudiante.id.in_(estudiantes_ids))
			else:
				# Si no hay estudiantes con calificaciones en esta materia, retornar lista vacía
				query = query.filter(Estudiante.id == -1)  # Condición imposible
	
	estudiantes = query.order_by(Estudiante.matricula).all()
	
	return render_template(
		"estudiantes_list.html", 
		estudiantes=estudiantes, 
		carreras=carreras,
		materias=materias,
		materia_carrera_map=materia_carrera_map,
		carrera_id_selected=carrera_id,
		materia_id_selected=materia_id
	)


@data_bp.route("/estudiantes/create", methods=["POST"])
@login_required
def estudiantes_create():
	matricula = request.form.get("matricula", "").strip()
	apellido_paterno = request.form.get("apellido_paterno", "").strip()
	apellido_materno = request.form.get("apellido_materno", "").strip()
	nombres = request.form.get("nombres", "").strip()
	genero = request.form.get("genero", "").strip()
	modalidad = request.form.get("modalidad", "").strip()
	carrera_id = request.form.get("carrera_id", "").strip()
	semestre = int(request.form.get("semestre", 1))
	
	# Si es docente, solo puede crear estudiantes de su carrera
	if not current_user.is_admin():
		if not current_user.carrera_rel:
			flash("No tienes una carrera asignada", "warning")
			return redirect(url_for("data.estudiantes_list"))
		# Forzar que el estudiante sea de su carrera
		carrera_id = str(current_user.carrera_id)
	
	if not (matricula and apellido_paterno and apellido_materno and nombres and carrera_id and semestre):
		flash("Datos incompletos", "warning")
		return redirect(url_for("data.estudiantes_list"))
	if Estudiante.query.filter_by(matricula=matricula).first():
		flash("La matrícula ya existe", "danger")
		return redirect(url_for("data.estudiantes_list"))
	carrera = Carrera.query.get(int(carrera_id))
	if not carrera:
		flash("Selecciona una carrera válida", "warning")
		return redirect(url_for("data.estudiantes_list"))
	
	# Verificar que el docente tenga permiso para esta carrera
	if not current_user.is_admin():
		if carrera.nombre != obtener_carrera_docente():
			flash("No tienes permiso para crear estudiantes de esa carrera", "warning")
			return redirect(url_for("data.estudiantes_list"))
	est = Estudiante(
		matricula=matricula,
		apellido_paterno=apellido_paterno,
		apellido_materno=apellido_materno,
		nombres=nombres,
		genero=genero,
		modalidad=modalidad,
		carrera=carrera.nombre,
		semestre=semestre
	)
	db.session.add(est)
	db.session.commit()
	registrar_auditoria(
		accion="CREATE",
		entidad="Estudiante",
		entidad_id=est.id,
		descripcion=f"Estudiante creado: {apellido_paterno} {apellido_materno} {nombres} (Matrícula: {matricula})",
		datos_nuevos={
			"matricula": matricula,
			"apellido_paterno": apellido_paterno,
			"apellido_materno": apellido_materno,
			"nombres": nombres,
			"carrera": carrera.nombre,
			"semestre": semestre,
			"estado": est.estado
		}
	)
	flash("Estudiante creado", "success")
	return redirect(url_for("data.estudiantes_list"))


@data_bp.route("/estudiantes/<int:est_id>/factores", methods=["GET", "POST"])
@login_required
def factores_estudiante(est_id: int):
	est = Estudiante.query.get_or_404(est_id)
	# Validar que solo desertores puedan acceder a factores
	if est.estado != "Desertor":
		flash("Los factores de riesgo solo están disponibles para estudiantes con estado 'Desertor'", "warning")
		return redirect(url_for("data.estudiantes_list"))
	factores = FactorRiesgo.query.filter_by(estudiante_id=est.id).order_by(FactorRiesgo.periodo.desc()).all()
	if request.method == "POST":
		tipo = request.form.get("tipo", "").strip()
		valor = request.form.get("valor", "").strip()
		periodo = request.form.get("periodo", "").strip()
		if not (tipo and valor and periodo):
			flash("Todos los campos de factor son obligatorios", "warning")
			return redirect(url_for("data.factores_estudiante", est_id=est.id))
		# Solo un factor principal por periodo (por seguridad)
		if FactorRiesgo.query.filter_by(estudiante_id=est.id, periodo=periodo, tipo=tipo).first():
			flash("Ya existe un factor de este tipo para ese periodo.", "danger")
			return redirect(url_for("data.factores_estudiante", est_id=est.id))
		f = FactorRiesgo(estudiante_id=est.id, tipo=tipo, valor=valor, periodo=periodo)
		db.session.add(f)
		db.session.commit()
		descripcion = f"Factor de riesgo creado para {est.apellido_paterno} {est.apellido_materno} {est.nombres} - Tipo: {tipo}, Valor: {valor}, Periodo: {periodo}"
		registrar_auditoria(
			accion="CREATE",
			entidad="FactorRiesgo",
			entidad_id=f.id,
			descripcion=descripcion,
			datos_nuevos={"estudiante_id": est.id, "tipo": tipo, "valor": valor, "periodo": periodo}
		)
		flash("Motivo registrado", "success")
		return redirect(url_for("data.factores_estudiante", est_id=est.id))
	return render_template("factores_list.html", e=est, factores=factores)


@data_bp.route("/factores/<int:fac_id>/edit", methods=["POST"])
@login_required
def factores_edit(fac_id: int):
	f = FactorRiesgo.query.get_or_404(fac_id)
	# Validar que el estudiante sea desertor
	if f.estudiante.estado != "Desertor":
		flash("Los factores de riesgo solo están disponibles para estudiantes con estado 'Desertor'", "warning")
		return redirect(url_for("data.estudiantes_list"))
	tipo = request.form.get("tipo", f.tipo).strip()
	valor = request.form.get("valor", f.valor).strip()
	periodo = request.form.get("periodo", f.periodo).strip()
	if not (tipo and valor and periodo):
		flash("Todos los campos son obligatorios", "warning")
		return redirect(url_for("data.factores_estudiante", est_id=f.estudiante_id))
	# Checar que no choque otro factor igual en mismo periodo
	dup = FactorRiesgo.query.filter(
		FactorRiesgo.estudiante_id == f.estudiante_id,
		FactorRiesgo.id != f.id,
		FactorRiesgo.periodo == periodo,
		FactorRiesgo.tipo == tipo
	).first()
	if dup:
		flash("Ya existe ese factor para el periodo.", "danger")
		return redirect(url_for("data.factores_estudiante", est_id=f.estudiante_id))
	datos_anteriores = {"tipo": f.tipo, "valor": f.valor, "periodo": f.periodo}
	f.tipo = tipo
	f.valor = valor
	f.periodo = periodo
	db.session.commit()
	est = Estudiante.query.get(f.estudiante_id)
	descripcion = f"Factor de riesgo actualizado para {est.apellido_paterno} {est.apellido_materno} {est.nombres} - Tipo: {tipo}, Valor: {valor}, Periodo: {periodo}"
	registrar_auditoria(
		accion="UPDATE",
		entidad="FactorRiesgo",
		entidad_id=f.id,
		descripcion=descripcion,
		datos_anteriores=datos_anteriores,
		datos_nuevos={"tipo": tipo, "valor": valor, "periodo": periodo}
	)
	flash("Factor actualizado", "success")
	return redirect(url_for("data.factores_estudiante", est_id=f.estudiante_id))


@data_bp.route("/factores/<int:fac_id>/delete", methods=["POST"])
@login_required
def factores_delete(fac_id: int):
	f = FactorRiesgo.query.get_or_404(fac_id)
	# Validar que el estudiante sea desertor
	if f.estudiante.estado != "Desertor":
		flash("Los factores de riesgo solo están disponibles para estudiantes con estado 'Desertor'", "warning")
		return redirect(url_for("data.estudiantes_list"))
	est_id = f.estudiante_id
	est = Estudiante.query.get(est_id)
	datos_eliminados = {"tipo": f.tipo, "valor": f.valor, "periodo": f.periodo}
	db.session.delete(f)
	db.session.commit()
	descripcion = f"Factor de riesgo eliminado para {est.apellido_paterno} {est.apellido_materno} {est.nombres} - Tipo: {f.tipo}, Periodo: {f.periodo}"
	registrar_auditoria(
		accion="DELETE",
		entidad="FactorRiesgo",
		entidad_id=fac_id,
		descripcion=descripcion,
		datos_anteriores=datos_eliminados
	)
	flash("Factor eliminado", "success")
	return redirect(url_for("data.factores_estudiante", est_id=est_id))


# Cambios en la edición de estudiante: Si estado = Desertor y no tiene factor, redirige a factores
@data_bp.route("/estudiantes/<int:est_id>/edit", methods=["GET", "POST"])
@login_required
def estudiantes_edit(est_id: int):
	est = Estudiante.query.get_or_404(est_id)
	
	# Si es docente, verificar que el estudiante sea de su carrera
	if not current_user.is_admin():
		carrera_docente = obtener_carrera_docente()
		if carrera_docente and est.carrera != carrera_docente:
			flash("No tienes permiso para editar este estudiante", "warning")
			return redirect(url_for("data.estudiantes_list"))
	
	if request.method == "POST":
		datos_anteriores = {
			"matricula": est.matricula,
			"apellido_paterno": est.apellido_paterno,
			"apellido_materno": est.apellido_materno,
			"nombres": est.nombres,
			"genero": est.genero,
			"modalidad": est.modalidad,
			"carrera": est.carrera,
			"semestre": est.semestre,
			"estado": est.estado
		}
		est.matricula = request.form.get("matricula", est.matricula).strip()
		est.apellido_paterno = request.form.get("apellido_paterno", est.apellido_paterno).strip()
		est.apellido_materno = request.form.get("apellido_materno", est.apellido_materno).strip()
		est.nombres = request.form.get("nombres", est.nombres).strip()
		est.genero = request.form.get("genero", est.genero).strip()
		est.modalidad = request.form.get("modalidad", est.modalidad).strip()
		carrera_id = request.form.get("carrera_id", "").strip()
		if carrera_id:
			car = Carrera.query.get(int(carrera_id))
			if not car:
				flash("Selecciona una carrera válida", "warning")
				return redirect(url_for("data.estudiantes_edit", est_id=est.id))
			
			# Si es docente, verificar que solo pueda cambiar a su carrera
			if not current_user.is_admin():
				carrera_docente = obtener_carrera_docente()
				if car.nombre != carrera_docente:
					flash("No tienes permiso para cambiar la carrera de este estudiante", "warning")
					return redirect(url_for("data.estudiantes_edit", est_id=est.id))
			
			est.carrera = car.nombre
		est.semestre = int(request.form.get("semestre", est.semestre))
		est.estado = request.form.get("estado", est.estado).strip()
		db.session.commit()
		registrar_auditoria(
			accion="UPDATE",
			entidad="Estudiante",
			entidad_id=est.id,
			descripcion=f"Estudiante actualizado: {est.apellido_paterno} {est.apellido_materno} {est.nombres} (Matrícula: {est.matricula})",
			datos_anteriores=datos_anteriores,
			datos_nuevos={
				"matricula": est.matricula,
				"apellido_paterno": est.apellido_paterno,
				"apellido_materno": est.apellido_materno,
				"nombres": est.nombres,
				"genero": est.genero,
				"modalidad": est.modalidad,
				"carrera": est.carrera,
				"semestre": est.semestre,
				"estado": est.estado
			}
		)
		# Si es desertor Y no tiene factor, redirige a factor de riesgo obligatorio
		if est.estado == "Desertor":
			factors_count = FactorRiesgo.query.filter_by(estudiante_id=est.id).count()
			if factors_count == 0:
				flash("Es obligatorio capturar al menos un motivo principal de deserción","info")
				return redirect(url_for("data.factores_estudiante", est_id=est.id))
		flash("Estudiante actualizado", "success")
		return redirect(url_for("data.estudiantes_list"))
	
	# Filtrar carreras según el rol del usuario
	if current_user.is_admin():
		carreras = Carrera.query.order_by(Carrera.nombre).all()
	else:
		# Docentes solo ven su carrera
		if current_user.carrera_rel:
			carreras = [current_user.carrera_rel]
		else:
			carreras = []
	
	return render_template("estudiantes_edit.html", e=est, carreras=carreras)


@data_bp.route("/estudiantes/<int:est_id>/delete", methods=["POST"])
@login_required
def estudiantes_delete(est_id: int):
	est = Estudiante.query.get_or_404(est_id)
	
	# Si es docente, verificar que el estudiante sea de su carrera
	if not current_user.is_admin():
		carrera_docente = obtener_carrera_docente()
		if carrera_docente and est.carrera != carrera_docente:
			flash("No tienes permiso para eliminar este estudiante", "warning")
			return redirect(url_for("data.estudiantes_list"))
	
	nombre_completo = f"{est.apellido_paterno} {est.apellido_materno} {est.nombres}"
	datos_eliminados = {
		"matricula": est.matricula,
		"apellido_paterno": est.apellido_paterno,
		"apellido_materno": est.apellido_materno,
		"nombres": est.nombres,
		"carrera": est.carrera,
		"semestre": est.semestre,
		"estado": est.estado
	}
	db.session.delete(est)
	db.session.commit()
	registrar_auditoria(
		accion="DELETE",
		entidad="Estudiante",
		entidad_id=est_id,
		descripcion=f"Estudiante eliminado: {nombre_completo} (Matrícula: {est.matricula})",
		datos_anteriores=datos_eliminados
	)
	flash("Estudiante eliminado", "success")
	return redirect(url_for("data.estudiantes_list"))


# -------- CRUD Materias --------
@data_bp.route("/materias")
@login_required
def materias_list():
	# Filtrar carreras según el rol del usuario
	if current_user.is_admin():
		carreras = Carrera.query.order_by(Carrera.nombre).all()
		materias = Materia.query.order_by(Materia.semestre, Materia.nombre).all()
	else:
		# Docentes solo ven su carrera
		if current_user.carrera_rel:
			carreras = [current_user.carrera_rel]
			carrera_obj = current_user.carrera_rel
			materias = Materia.query.filter(
				(Materia.carrera_id == carrera_obj.id) | (Materia.carrera_id == None)
			).order_by(Materia.semestre, Materia.nombre).all()
		else:
			carreras = []
			materias = []
	
	# Cargar relaciones de carrera para evitar queries N+1
	for m in materias:
		if m.carrera_id:
			_ = m.carrera_rel  # fuerza carga de relación
	return render_template("materias_list.html", materias=materias, carreras=carreras)


@data_bp.route("/materias/create", methods=["POST"])
@login_required
def materias_create():
	nombre = request.form.get("nombre", "").strip()
	semestre = int(request.form.get("semestre", 1))
	carrera_id = request.form.get("carrera_id", "").strip() or None
	
	# Si es docente, solo puede crear materias de su carrera
	if not current_user.is_admin():
		if not current_user.carrera_rel:
			flash("No tienes una carrera asignada", "warning")
			return redirect(url_for("data.materias_list"))
		# Forzar que la materia sea de su carrera
		carrera_id = current_user.carrera_id
	
	if not nombre:
		flash("Nombre requerido", "warning")
		return redirect(url_for("data.materias_list"))
	if carrera_id:
		carrera_id = int(carrera_id)
		# Verificar que el docente tenga permiso para esta carrera
		if not current_user.is_admin():
			if carrera_id != current_user.carrera_id:
				flash("No tienes permiso para crear materias de esa carrera", "warning")
				return redirect(url_for("data.materias_list"))
		if Materia.query.filter_by(nombre=nombre, carrera_id=carrera_id).first():
			flash("La materia ya existe para esa carrera", "danger")
			return redirect(url_for("data.materias_list"))
	else:
		if Materia.query.filter_by(nombre=nombre, carrera_id=None).first():
			flash("La materia ya existe sin carrera asignada", "danger")
			return redirect(url_for("data.materias_list"))
	m = Materia(nombre=nombre, semestre=semestre, carrera_id=carrera_id)
	db.session.add(m)
	db.session.commit()
	descripcion = f"Materia creada: {nombre} (Semestre: {semestre})"
	if carrera_id:
		car = Carrera.query.get(carrera_id)
		if car:
			descripcion += f" - Carrera: {car.nombre}"
	registrar_auditoria(
		accion="CREATE",
		entidad="Materia",
		entidad_id=m.id,
		descripcion=descripcion,
		datos_nuevos={"nombre": nombre, "semestre": semestre, "carrera_id": carrera_id}
	)
	flash("Materia creada", "success")
	return redirect(url_for("data.materias_list"))


@data_bp.route("/materias/<int:mat_id>/edit", methods=["POST"])
@login_required
def materias_edit(mat_id: int):
	m = Materia.query.get_or_404(mat_id)
	
	# Si es docente, verificar que la materia sea de su carrera
	if not current_user.is_admin():
		if m.carrera_id and m.carrera_id != current_user.carrera_id:
			flash("No tienes permiso para editar esta materia", "warning")
			return redirect(url_for("data.materias_list"))
	
	datos_anteriores = {"nombre": m.nombre, "semestre": m.semestre, "carrera_id": m.carrera_id}
	m.nombre = request.form.get("nombre", m.nombre).strip()
	m.semestre = int(request.form.get("semestre", m.semestre))
	carrera_id = request.form.get("carrera_id", "").strip() or None
	
	# Si es docente, solo puede asignar su carrera
	if not current_user.is_admin():
		if not current_user.carrera_rel:
			flash("No tienes una carrera asignada", "warning")
			return redirect(url_for("data.materias_list"))
		carrera_id = current_user.carrera_id
	
	if carrera_id:
		carrera_id = int(carrera_id)
		# Verificar que el docente tenga permiso para esta carrera
		if not current_user.is_admin():
			if carrera_id != current_user.carrera_id:
				flash("No tienes permiso para asignar esa carrera", "warning")
				return redirect(url_for("data.materias_list"))
		dup = Materia.query.filter(
			Materia.id != m.id,
			Materia.nombre == m.nombre,
			Materia.carrera_id == carrera_id
		).first()
		if dup:
			flash("Ya existe esa materia para esa carrera", "danger")
			return redirect(url_for("data.materias_list"))
	m.carrera_id = carrera_id
	db.session.commit()
	descripcion = f"Materia actualizada: {m.nombre} (Semestre: {m.semestre})"
	if carrera_id:
		car = Carrera.query.get(carrera_id)
		if car:
			descripcion += f" - Carrera: {car.nombre}"
	registrar_auditoria(
		accion="UPDATE",
		entidad="Materia",
		entidad_id=m.id,
		descripcion=descripcion,
		datos_anteriores=datos_anteriores,
		datos_nuevos={"nombre": m.nombre, "semestre": m.semestre, "carrera_id": carrera_id}
	)
	flash("Materia actualizada", "success")
	return redirect(url_for("data.materias_list"))


@data_bp.route("/materias/<int:mat_id>/delete", methods=["POST"])
@login_required
def materias_delete(mat_id: int):
	m = Materia.query.get_or_404(mat_id)
	
	# Si es docente, verificar que la materia sea de su carrera
	if not current_user.is_admin():
		if m.carrera_id and m.carrera_id != current_user.carrera_id:
			flash("No tienes permiso para eliminar esta materia", "warning")
			return redirect(url_for("data.materias_list"))
	
	nombre_materia = m.nombre
	datos_eliminados = {"nombre": m.nombre, "semestre": m.semestre, "carrera_id": m.carrera_id}
	db.session.delete(m)
	db.session.commit()
	registrar_auditoria(
		accion="DELETE",
		entidad="Materia",
		entidad_id=mat_id,
		descripcion=f"Materia eliminada: {nombre_materia}",
		datos_anteriores=datos_eliminados
	)
	flash("Materia eliminada", "success")
	return redirect(url_for("data.materias_list"))


# -------- Calificaciones por estudiante --------
@data_bp.route("/estudiantes/<int:est_id>/calificaciones")
@login_required
def calificaciones_estudiante(est_id: int):
	est = Estudiante.query.get_or_404(est_id)
	
	# Obtener la carrera del estudiante
	carrera_estudiante = Carrera.query.filter_by(nombre=est.carrera).first()
	
	# Filtrar materias: solo las que pertenecen a la carrera del estudiante o no tienen carrera específica
	if carrera_estudiante:
		materias = Materia.query.filter(
			(Materia.carrera_id == carrera_estudiante.id) | (Materia.carrera_id == None)
		).order_by(Materia.semestre, Materia.nombre).all()
	else:
		# Si no se encuentra la carrera, mostrar solo materias sin carrera específica
		materias = Materia.query.filter(Materia.carrera_id == None).order_by(Materia.semestre, Materia.nombre).all()
	
	cals = Calificacion.query.filter_by(estudiante_id=est.id).all()
	return render_template("calificaciones_list.html", e=est, materias=materias, calificaciones=cals)


@data_bp.route("/estudiantes/<int:est_id>/calificaciones/create", methods=["POST"])
@login_required
def calificaciones_create(est_id: int):
	est = Estudiante.query.get_or_404(est_id)
	materia_id = int(request.form.get("materia_id"))
	nota = float(request.form.get("nota"))
	asistencia = float(request.form.get("asistencia"))
	periodo = request.form.get("periodo", "").strip()
	
	# Validar que la materia pertenezca a la carrera del estudiante
	materia = Materia.query.get_or_404(materia_id)
	carrera_estudiante = Carrera.query.filter_by(nombre=est.carrera).first()
	
	if carrera_estudiante:
		# La materia debe pertenecer a la carrera del estudiante o no tener carrera específica
		if materia.carrera_id is not None and materia.carrera_id != carrera_estudiante.id:
			flash("La materia seleccionada no pertenece a la carrera del estudiante", "warning")
			return redirect(url_for("data.calificaciones_estudiante", est_id=est.id))
	else:
		# Si el estudiante no tiene carrera válida, solo permitir materias sin carrera específica
		if materia.carrera_id is not None:
			flash("La materia seleccionada no pertenece a la carrera del estudiante", "warning")
			return redirect(url_for("data.calificaciones_estudiante", est_id=est.id))
	
	# Validar rango de nota (0-100)
	if not (0 <= nota <= 100):
		flash("La calificación debe estar entre 0 y 100", "warning")
		return redirect(url_for("data.calificaciones_estudiante", est_id=est.id))
	# Validar rango de asistencia (0-100)
	if not (0 <= asistencia <= 100):
		flash("La asistencia debe estar entre 0 y 100", "warning")
		return redirect(url_for("data.calificaciones_estudiante", est_id=est.id))
	# Validar duplicado (misma materia y periodo para el mismo estudiante)
	exists = Calificacion.query.filter_by(estudiante_id=est.id, materia_id=materia_id, periodo=periodo).first()
	if exists:
		flash("Este alumno ya tiene esa materia en el mismo periodo.", "warning")
		return redirect(url_for("data.calificaciones_estudiante", est_id=est.id))
	cal = Calificacion(estudiante_id=est.id, materia_id=materia_id, nota=nota, asistencia=asistencia, periodo=periodo)
	db.session.add(cal)
	db.session.commit()
	mat = Materia.query.get(materia_id)
	descripcion = f"Calificación creada para {est.apellido_paterno} {est.apellido_materno} {est.nombres} - {mat.nombre if mat else 'N/A'} (Nota: {nota}, Asistencia: {asistencia}, Periodo: {periodo})"
	registrar_auditoria(
		accion="CREATE",
		entidad="Calificacion",
		entidad_id=cal.id,
		descripcion=descripcion,
		datos_nuevos={
			"estudiante_id": est.id,
			"materia_id": materia_id,
			"nota": nota,
			"asistencia": asistencia,
			"periodo": periodo
		}
	)
	flash("Calificación agregada", "success")
	return redirect(url_for("data.calificaciones_estudiante", est_id=est.id))


@data_bp.route("/calificaciones/<int:cal_id>/edit", methods=["POST"])
@login_required
def calificaciones_edit(cal_id: int):
	cal = Calificacion.query.get_or_404(cal_id)
	est = Estudiante.query.get_or_404(cal.estudiante_id)
	new_materia_id = int(request.form.get("materia_id", cal.materia_id))
	new_periodo = request.form.get("periodo", cal.periodo).strip()
	new_nota = float(request.form.get("nota", cal.nota))
	new_asistencia = float(request.form.get("asistencia", cal.asistencia))
	
	# Validar que la materia pertenezca a la carrera del estudiante
	materia = Materia.query.get_or_404(new_materia_id)
	carrera_estudiante = Carrera.query.filter_by(nombre=est.carrera).first()
	
	if carrera_estudiante:
		# La materia debe pertenecer a la carrera del estudiante o no tener carrera específica
		if materia.carrera_id is not None and materia.carrera_id != carrera_estudiante.id:
			flash("La materia seleccionada no pertenece a la carrera del estudiante", "warning")
			return redirect(url_for("data.calificaciones_estudiante", est_id=cal.estudiante_id))
	else:
		# Si el estudiante no tiene carrera válida, solo permitir materias sin carrera específica
		if materia.carrera_id is not None:
			flash("La materia seleccionada no pertenece a la carrera del estudiante", "warning")
			return redirect(url_for("data.calificaciones_estudiante", est_id=cal.estudiante_id))
	
	# Validar rango de nota (0-100)
	if not (0 <= new_nota <= 100):
		flash("La calificación debe estar entre 0 y 100", "warning")
		return redirect(url_for("data.calificaciones_estudiante", est_id=cal.estudiante_id))
	# Validar rango de asistencia (0-100)
	if not (0 <= new_asistencia <= 100):
		flash("La asistencia debe estar entre 0 y 100", "warning")
		return redirect(url_for("data.calificaciones_estudiante", est_id=cal.estudiante_id))
	# Validar duplicado si cambian materia o periodo
	dup = Calificacion.query.filter(
		Calificacion.estudiante_id == cal.estudiante_id,
		Calificacion.materia_id == new_materia_id,
		Calificacion.periodo == new_periodo,
		Calificacion.id != cal.id,
	).first()
	if dup:
		flash("Duplicado: ya existe esa materia en ese periodo para el alumno.", "warning")
		return redirect(url_for("data.calificaciones_estudiante", est_id=cal.estudiante_id))
	datos_anteriores = {
		"materia_id": cal.materia_id,
		"nota": cal.nota,
		"asistencia": cal.asistencia,
		"periodo": cal.periodo
	}
	cal.materia_id = new_materia_id
	cal.nota = new_nota
	cal.asistencia = new_asistencia
	cal.periodo = new_periodo
	db.session.commit()
	mat = Materia.query.get(new_materia_id)
	est = Estudiante.query.get(cal.estudiante_id)
	descripcion = f"Calificación actualizada para {est.apellido_paterno} {est.apellido_materno} {est.nombres} - {mat.nombre if mat else 'N/A'} (Nota: {new_nota}, Asistencia: {new_asistencia}, Periodo: {new_periodo})"
	registrar_auditoria(
		accion="UPDATE",
		entidad="Calificacion",
		entidad_id=cal.id,
		descripcion=descripcion,
		datos_anteriores=datos_anteriores,
		datos_nuevos={
			"materia_id": new_materia_id,
			"nota": new_nota,
			"asistencia": new_asistencia,
			"periodo": new_periodo
		}
	)
	flash("Calificación actualizada", "success")
	return redirect(url_for("data.calificaciones_estudiante", est_id=cal.estudiante_id))


@data_bp.route("/calificaciones/<int:cal_id>/delete", methods=["POST"])
@login_required
def calificaciones_delete(cal_id: int):
	cal = Calificacion.query.get_or_404(cal_id)
	est_id = cal.estudiante_id
	est = Estudiante.query.get(est_id)
	mat = Materia.query.get(cal.materia_id)
	datos_eliminados = {
		"materia_id": cal.materia_id,
		"nota": cal.nota,
		"asistencia": cal.asistencia,
		"periodo": cal.periodo
	}
	db.session.delete(cal)
	db.session.commit()
	descripcion = f"Calificación eliminada para {est.apellido_paterno} {est.apellido_materno} {est.nombres} - {mat.nombre if mat else 'N/A'} (Periodo: {cal.periodo})"
	registrar_auditoria(
		accion="DELETE",
		entidad="Calificacion",
		entidad_id=cal_id,
		descripcion=descripcion,
		datos_anteriores=datos_eliminados
	)
	flash("Calificación eliminada", "success")
	return redirect(url_for("data.calificaciones_estudiante", est_id=est_id))


# -------- Auditoría --------
@data_bp.route("/auditoria")
@login_required
def auditoria_list():
	# Solo administradores pueden ver auditoría
	if not current_user.is_admin():
		flash("No tienes permiso para acceder a esta sección", "warning")
		return redirect(url_for("main.index"))
	"""Muestra todos los registros de auditoría del sistema"""
	logs = Auditoria.query.order_by(Auditoria.fecha.desc()).limit(500).all()
	return render_template("auditoria_list.html", logs=logs)


@data_bp.route("/auditoria/<string:entidad>/<int:entidad_id>")
@login_required
def auditoria_entidad(entidad: str, entidad_id: int):
	# Solo administradores pueden ver detalles de auditoría
	if not current_user.is_admin():
		flash("No tienes permiso para acceder a esta sección", "warning")
		return redirect(url_for("main.index"))
	"""Muestra los logs de auditoría para una entidad específica"""
	logs = Auditoria.query.filter_by(
		entidad=entidad,
		entidad_id=entidad_id
	).order_by(Auditoria.fecha.desc()).all()
	return render_template("auditoria_list.html", logs=logs, filtro_entidad=entidad, filtro_id=entidad_id)


# -------- Importación desde Excel --------
@data_bp.route("/import", methods=["GET", "POST"])
@login_required
def importar_excel():
	# Solo administradores pueden importar Excel
	if not current_user.is_admin():
		flash("No tienes permiso para acceder a esta sección", "warning")
		return redirect(url_for("main.index"))
	
	if request.method == "POST":
		archivo = request.files.get("archivo")
		if not archivo:
			flash("Sube un archivo .xlsx", "warning")
			return redirect(url_for("data.importar_excel"))
		df = pd.read_excel(archivo)
		# Normalizar nombres de columna
		df.columns = [c.lower() for c in df.columns]
		# Validación: debe tener mínimo matricula, carrera, semestre, materia, nota, asistencia, periodo
		req_cols = {"matricula", "carrera", "semestre", "materia", "nota", "asistencia", "periodo"}
		if not req_cols.issubset(set(df.columns)):
			flash("Columnas requeridas: matricula,carrera,semestre,materia,nota,asistencia,periodo. Opcional: nombre (o apellido_paterno,apellido_materno,nombres)", "danger")
			return redirect(url_for("data.importar_excel"))
		# Limpiar datos
		df = df.dropna(subset=list(req_cols))
		df = df[(df["nota"].between(0, 100)) & (df["asistencia"].between(0, 100))]

		insertados = 0
		dups = 0
		for _, row in df.iterrows():
			matricula = str(row["matricula"]).strip()
			materia_nombre = str(row["materia"]).strip()
			periodo = str(row["periodo"]).strip()

			est = Estudiante.query.filter_by(matricula=matricula).first()
			if not est:
				# Manejar nombres: si vienen separados, usarlos; si solo viene "nombre", ponerlo en nombres
				if "apellido_paterno" in df.columns and "apellido_materno" in df.columns and "nombres" in df.columns:
					apellido_paterno = str(row.get("apellido_paterno", "")).strip() or "Sin apellido"
					apellido_materno = str(row.get("apellido_materno", "")).strip() or "Sin apellido"
					nombres = str(row.get("nombres", "")).strip() or "Sin nombre"
				elif "nombre" in df.columns:
					apellido_paterno = "Sin apellido"
					apellido_materno = "Sin apellido"
					nombres = str(row.get("nombre", "")).strip() or "Sin nombre"
				else:
					apellido_paterno = "Sin apellido"
					apellido_materno = "Sin apellido"
					nombres = "Sin nombre"
				est = Estudiante(
					matricula=matricula,
					apellido_paterno=apellido_paterno,
					apellido_materno=apellido_materno,
					nombres=nombres,
					carrera=str(row["carrera"]).strip(),
					semestre=int(row["semestre"]),
				)
				db.session.add(est)

			mat = Materia.query.filter_by(nombre=materia_nombre).first()
			if not mat:
				mat = Materia(nombre=materia_nombre, semestre=int(row.get("semestre", 1)))
				db.session.add(mat)

			# Evitar duplicados por alumno-materia-periodo
			if Calificacion.query.filter_by(estudiante_id=est.id, materia_id=mat.id, periodo=periodo).first():
				dups += 1
				continue

			cal = Calificacion(
				estudiante=est,
				materia=mat,
				nota=float(row["nota"]),
				asistencia=float(row["asistencia"]),
				periodo=periodo,
			)
			db.session.add(cal)
			insertados += 1

		db.session.commit()
		msg = f"Registros importados: {insertados}"
		if dups:
			msg += f" · Duplicados omitidos: {dups}"
		flash(msg, "success")
		return redirect(url_for("main.index"))
	return render_template("importar.html")


# --------- Gráficas de Calidad ---------
@data_bp.route("/charts/pareto")
@login_required
def chart_pareto():
	try:
		# Obtener filtro de semestre de la URL
		semestre = request.args.get("semestre", "").strip()
		
		# Análisis general de factores de deserción (solo de desertores)
		# Unir con Estudiante para asegurar que solo contamos factores de desertores
		query = db.session.query(
			FactorRiesgo.tipo,
			db.func.count(FactorRiesgo.id)
		).join(
			Estudiante, FactorRiesgo.estudiante_id == Estudiante.id
		).filter(
			Estudiante.estado == "Desertor"
		)
		
		# Aplicar filtro por carrera si es docente
		if not current_user.is_admin():
			carrera_nombre = obtener_carrera_docente()
			if carrera_nombre:
				query = query.filter(Estudiante.carrera == carrera_nombre)
		
		# Aplicar filtro por semestre si se proporciona
		if semestre:
			try:
				semestre_int = int(semestre)
				query = query.filter(Estudiante.semestre == semestre_int)
			except ValueError:
				pass  # Si el semestre no es válido, ignorar el filtro
		
		q = query.group_by(
			FactorRiesgo.tipo
		).order_by(
			db.func.count(FactorRiesgo.id).desc()
		).all()
		
		if not q:
			# Crear gráfico vacío con mensaje
			fig = go.Figure()
			fig.add_annotation(
				x=0.5, y=0.5,
				text="No hay factores de riesgo registrados.<br>Registra factores para los estudiantes desertores.",
				showarrow=False,
				font=dict(size=14, color='#f5f5f7'),
				xref="paper", yref="paper"
			)
			fig.update_layout(title="Análisis de Pareto - Factores de Deserción", xaxis=dict(visible=False), yaxis=dict(visible=False))
			fig = apply_dark_theme(fig)
			return jsonify(fig.to_dict())
		
		labels = [str(r[0]) for r in q]
		counts = [int(r[1]) for r in q]
		
		# Crear gráfico de barras
		fig = go.Figure()
		fig.add_trace(go.Bar(x=labels, y=counts, name="Frecuencia", marker_color='#0071e3'))
		
		# Agregar línea acumulada
		if counts:
			cum_sum = 0
			cum_pct = []
			total = sum(counts)
			for count in counts:
				cum_sum += count
				cum_pct.append(100 * cum_sum / total)
			
			fig.add_trace(go.Scatter(
				x=labels,
				y=cum_pct,
				mode="lines+markers",
				name="Acumulado %",
				yaxis="y2",
				line=dict(color="#ff3b30", width=2),
				marker=dict(color="#ff3b30")
			))
			fig.update_layout(
				title="Análisis de Pareto - Factores de Deserción",
				xaxis=dict(title="Tipo de Factor", tickangle=-45),
				yaxis=dict(title="Frecuencia"),
				yaxis2=dict(
					overlaying="y", 
					side="right", 
					range=[0, 100], 
					title="% Acumulado",
					gridcolor='rgba(255, 255, 255, 0.1)',
					tickfont=dict(color='#86868b'),
					titlefont=dict(color='#f5f5f7')
				),
			)
		
		fig = apply_dark_theme(fig)
		return jsonify(fig.to_dict())
	except Exception as e:
		# En caso de error, retornar gráfico vacío con mensaje de error
		fig = go.Figure()
		fig.add_annotation(
			x=0.5, y=0.5,
			text=f"Error al generar gráfico: {str(e)}",
			showarrow=False,
			font=dict(size=12, color='#f5f5f7'),
			xref="paper", yref="paper"
		)
		fig.update_layout(title="Error", xaxis=dict(visible=False), yaxis=dict(visible=False))
		fig = apply_dark_theme(fig)
		return jsonify(fig.to_dict())


@data_bp.route("/charts/histograma")
@login_required
def chart_histograma():
	query_calificaciones = Calificacion.query
	
	# Aplicar filtro por carrera si es docente
	if not current_user.is_admin():
		carrera_nombre = obtener_carrera_docente()
		if carrera_nombre:
			estudiantes_ids = db.session.query(Estudiante.id).filter(
				Estudiante.carrera == carrera_nombre
			).all()
			estudiantes_ids = [eid[0] for eid in estudiantes_ids]
			if estudiantes_ids:
				query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id.in_(estudiantes_ids))
			else:
				query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id == -1)
	
	notas = [c.nota for c in query_calificaciones.all()]
	if notas:
		fig = px.histogram(notas, nbins=10, title="Histograma de notas")
		fig.update_traces(marker_color='#0071e3')
	else:
		fig = go.Figure()
	fig = apply_dark_theme(fig)
	return jsonify(fig.to_dict())


@data_bp.route("/charts/dispersion")
@login_required
def chart_dispersion():
	try:
		# Dispersión Asistencia vs Nota
		query_calificaciones = Calificacion.query
		
		# Aplicar filtro por carrera si es docente
		if not current_user.is_admin():
			carrera_nombre = obtener_carrera_docente()
			if carrera_nombre:
				estudiantes_ids = db.session.query(Estudiante.id).filter(
					Estudiante.carrera == carrera_nombre
				).all()
				estudiantes_ids = [eid[0] for eid in estudiantes_ids]
				if estudiantes_ids:
					query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id.in_(estudiantes_ids))
				else:
					query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id == -1)
		
		calificaciones = query_calificaciones.all()
		if not calificaciones:
			fig = go.Figure()
			fig.add_annotation(
				x=0.5, y=0.5,
				text="No hay calificaciones registradas",
				showarrow=False,
				font=dict(size=14, color='#f5f5f7'),
				xref="paper", yref="paper"
			)
			fig.update_layout(title="Asistencia vs Nota", xaxis=dict(visible=False), yaxis=dict(visible=False))
			fig = apply_dark_theme(fig)
			return jsonify(fig.to_dict())
		
		# Crear listas de Python directamente (sin pandas)
		asistencias = [float(c.asistencia) for c in calificaciones]
		notas = [float(c.nota) for c in calificaciones]
		
		fig = go.Figure()
		fig.add_trace(go.Scatter(
			x=asistencias,
			y=notas,
			mode='markers',
			name='Datos',
			marker=dict(size=8, opacity=0.6, color='#0071e3')
		))
		fig.update_layout(
			title="Asistencia vs Calificación",
			xaxis=dict(title="Asistencia (%)"),
			yaxis=dict(title="Calificación")
		)
		fig = apply_dark_theme(fig)
		return jsonify(fig.to_dict())
	except Exception as e:
		fig = go.Figure()
		fig.add_annotation(
			x=0.5, y=0.5,
			text=f"Error: {str(e)}",
			showarrow=False,
			font=dict(size=12, color='#f5f5f7'),
			xref="paper", yref="paper"
		)
		fig.update_layout(title="Error", xaxis=dict(visible=False), yaxis=dict(visible=False))
		fig = apply_dark_theme(fig)
		return jsonify(fig.to_dict())


@data_bp.route("/charts/ishikawa")
@login_required
def chart_ishikawa():
	# Para simplificar: barra por tipo de causa (Ishikawa resumido)
	query = db.session.query(FactorRiesgo.tipo, db.func.count(FactorRiesgo.id))
	
	# Aplicar filtro por carrera si es docente
	if not current_user.is_admin():
		carrera_nombre = obtener_carrera_docente()
		if carrera_nombre:
			estudiantes_ids = db.session.query(Estudiante.id).filter(
				Estudiante.carrera == carrera_nombre
			).all()
			estudiantes_ids = [eid[0] for eid in estudiantes_ids]
			if estudiantes_ids:
				query = query.filter(FactorRiesgo.estudiante_id.in_(estudiantes_ids))
			else:
				query = query.filter(FactorRiesgo.estudiante_id == -1)
	
	q = query.group_by(FactorRiesgo.tipo).all()
	if not q:
		fig = go.Figure()
		fig = apply_dark_theme(fig)
		return jsonify(fig.to_dict())
	df = pd.DataFrame(q, columns=["tipo", "conteo"])
	fig = px.bar(df, x="tipo", y="conteo", title="Diagrama causa-efecto (resumen)")
	fig.update_traces(marker_color='#0071e3')
	fig = apply_dark_theme(fig)
	return jsonify(fig.to_dict())


# --------- Exportación ---------
@data_bp.route("/export/csv")
@login_required
def export_csv():
	# Obtener filtros de la URL
	carrera_id = request.args.get("carrera_id", "").strip()
	materia_id = request.args.get("materia_id", "").strip()
	formato = request.args.get("formato", "csv").strip().lower()  # csv o excel
	
	# Construir consulta base
	query = Estudiante.query
	
	# Aplicar filtro automático por carrera si es docente
	query = aplicar_filtro_carrera(query, Estudiante)
	
	# Aplicar filtro por carrera (si se especifica en la URL)
	if carrera_id:
		carrera = Carrera.query.get(int(carrera_id))
		if carrera:
			# Si es docente, verificar que la carrera sea la suya
			if not current_user.is_admin():
				carrera_docente = obtener_carrera_docente()
				if carrera.nombre != carrera_docente:
					flash("No tienes permiso para exportar esa carrera", "warning")
					return redirect(url_for("data.estudiantes_list"))
			query = query.filter(Estudiante.carrera == carrera.nombre)
	
	# Aplicar filtro por materia
	if materia_id:
		materia = Materia.query.get(int(materia_id))
		if materia:
			# Si es docente, verificar que la materia sea de su carrera
			if not current_user.is_admin() and materia.carrera_id:
				carrera_docente = obtener_carrera_docente()
				carrera_obj = Carrera.query.filter_by(nombre=carrera_docente).first()
				if carrera_obj and materia.carrera_id != carrera_obj.id:
					flash("No tienes permiso para exportar esa materia", "warning")
					return redirect(url_for("data.estudiantes_list"))
			
			# Obtener IDs de estudiantes que tienen calificaciones en esta materia
			estudiantes_ids = db.session.query(Calificacion.estudiante_id).filter(
				Calificacion.materia_id == materia.id
			).distinct().all()
			estudiantes_ids = [eid[0] for eid in estudiantes_ids]
			if estudiantes_ids:
				query = query.filter(Estudiante.id.in_(estudiantes_ids))
			else:
				# Si no hay estudiantes con calificaciones en esta materia, retornar lista vacía
				query = query.filter(Estudiante.id == -1)  # Condición imposible
	
	# Obtener estudiantes filtrados
	estudiantes = query.order_by(Estudiante.matricula).all()
	
	# Debug: verificar cantidad
	if not estudiantes:
		flash("No hay estudiantes para exportar con los filtros seleccionados", "info")
		return redirect(url_for("data.estudiantes_list"))
	
	# Construir el DataFrame
	rows = []
	for e in estudiantes:
		rows.append({
			"matricula": e.matricula,
			"apellido_paterno": e.apellido_paterno,
			"apellido_materno": e.apellido_materno,
			"nombres": e.nombres,
			"nombre_completo": f"{e.apellido_paterno} {e.apellido_materno} {e.nombres}",
			"genero": e.genero or "",
			"modalidad": e.modalidad or "",
			"carrera": e.carrera,
			"semestre": e.semestre,
			"estado": e.estado,
		})
	
	df = pd.DataFrame(rows)
	stream = BytesIO()
	
	if formato == "excel":
		# Exportar a Excel
		df.to_excel(stream, index=False, engine='openpyxl')
		stream.seek(0)
		flash(f"Excel exportado con {len(rows)} registro(s)", "success")
		return send_file(stream, as_attachment=True, download_name="datos_estudiantes.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	else:
		# Exportar a CSV (por defecto)
		df.to_csv(stream, index=False, encoding="utf-8-sig")
		stream.seek(0)
		flash(f"CSV exportado con {len(rows)} registro(s)", "success")
		return send_file(stream, as_attachment=True, download_name="datos_estudiantes.csv", mimetype="text/csv")


# --------- Exportación de Gráficas ---------
@data_bp.route("/charts/export/<chart_type>")
@login_required
def export_chart(chart_type):
	"""Exporta gráficas como imágenes PNG"""
	try:
		# Obtener parámetros de filtro
		semestre = request.args.get("semestre", "").strip()
		
		fig = None
		filename = ""
		
		if chart_type == "pareto":
			# Generar gráfico de Pareto
			query = db.session.query(
				FactorRiesgo.tipo,
				db.func.count(FactorRiesgo.id)
			).join(
				Estudiante, FactorRiesgo.estudiante_id == Estudiante.id
			).filter(
				Estudiante.estado == "Desertor"
			)
			
			if semestre:
				try:
					semestre_int = int(semestre)
					query = query.filter(Estudiante.semestre == semestre_int)
				except ValueError:
					pass
			
			q = query.group_by(FactorRiesgo.tipo).order_by(db.func.count(FactorRiesgo.id).desc()).all()
			
			if not q:
				flash("No hay datos para exportar", "warning")
				return redirect(url_for("main.index"))
			
			labels = [str(r[0]) for r in q]
			counts = [int(r[1]) for r in q]
			
			fig = go.Figure()
			fig.add_trace(go.Bar(x=labels, y=counts, name="Frecuencia", marker_color='#0071e3'))
			
			if counts:
				cum_sum = 0
				cum_pct = []
				total = sum(counts)
				for count in counts:
					cum_sum += count
					cum_pct.append(100 * cum_sum / total)
				
				fig.add_trace(go.Scatter(
					x=labels,
					y=cum_pct,
					mode="lines+markers",
					name="Acumulado %",
					yaxis="y2",
					line=dict(color="#ff3b30", width=2),
					marker=dict(color="#ff3b30")
				))
				fig.update_layout(
					title="Análisis de Pareto - Factores de Deserción",
					xaxis=dict(title="Tipo de Factor", tickangle=-45),
					yaxis=dict(title="Frecuencia"),
					yaxis2=dict(
						overlaying="y",
						side="right",
						range=[0, 100],
						title="% Acumulado"
					),
				)
			
			filename = "pareto_factores_desercion.png"
			
		elif chart_type == "histograma":
			# Generar histograma
			query_calificaciones = Calificacion.query
			
			# Aplicar filtro por carrera si es docente
			if not current_user.is_admin():
				carrera_nombre = obtener_carrera_docente()
				if carrera_nombre:
					estudiantes_ids = db.session.query(Estudiante.id).filter(
						Estudiante.carrera == carrera_nombre
					).all()
					estudiantes_ids = [eid[0] for eid in estudiantes_ids]
					if estudiantes_ids:
						query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id.in_(estudiantes_ids))
					else:
						query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id == -1)
			
			notas = [c.nota for c in query_calificaciones.all()]
			if not notas:
				flash("No hay datos para exportar", "warning")
				return redirect(url_for("main.index"))
			
			fig = px.histogram(notas, nbins=10, title="Distribución de calificaciones")
			fig.update_traces(marker_color='#0071e3')
			filename = "histograma_calificaciones.png"
			
		elif chart_type == "dispersion":
			# Generar gráfico de dispersión
			query_calificaciones = Calificacion.query
			
			# Aplicar filtro por carrera si es docente
			if not current_user.is_admin():
				carrera_nombre = obtener_carrera_docente()
				if carrera_nombre:
					estudiantes_ids = db.session.query(Estudiante.id).filter(
						Estudiante.carrera == carrera_nombre
					).all()
					estudiantes_ids = [eid[0] for eid in estudiantes_ids]
					if estudiantes_ids:
						query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id.in_(estudiantes_ids))
					else:
						query_calificaciones = query_calificaciones.filter(Calificacion.estudiante_id == -1)
			
			calificaciones = query_calificaciones.all()
			if not calificaciones:
				flash("No hay datos para exportar", "warning")
				return redirect(url_for("main.index"))
			
			asistencias = [float(c.asistencia) for c in calificaciones]
			notas = [float(c.nota) for c in calificaciones]
			
			fig = go.Figure()
			fig.add_trace(go.Scatter(
				x=asistencias,
				y=notas,
				mode='markers',
				name='Datos',
				marker=dict(size=8, opacity=0.6, color='#0071e3')
			))
			fig.update_layout(
				title="Asistencia vs Calificación",
				xaxis=dict(title="Asistencia (%)"),
				yaxis=dict(title="Calificación")
			)
			filename = "dispersion_asistencia_calificacion.png"
			
		elif chart_type == "ishikawa":
			# Generar gráfico de Ishikawa
			query = db.session.query(FactorRiesgo.tipo, db.func.count(FactorRiesgo.id))
			
			# Aplicar filtro por carrera si es docente
			if not current_user.is_admin():
				carrera_nombre = obtener_carrera_docente()
				if carrera_nombre:
					estudiantes_ids = db.session.query(Estudiante.id).filter(
						Estudiante.carrera == carrera_nombre
					).all()
					estudiantes_ids = [eid[0] for eid in estudiantes_ids]
					if estudiantes_ids:
						query = query.filter(FactorRiesgo.estudiante_id.in_(estudiantes_ids))
					else:
						query = query.filter(FactorRiesgo.estudiante_id == -1)
			
			q = query.group_by(FactorRiesgo.tipo).all()
			if not q:
				flash("No hay datos para exportar", "warning")
				return redirect(url_for("main.index"))
			
			df = pd.DataFrame(q, columns=["tipo", "conteo"])
			fig = px.bar(df, x="tipo", y="conteo", title="Diagrama causa-efecto (resumen)")
			fig.update_traces(marker_color='#0071e3')
			filename = "ishikawa_factores.png"
		else:
			flash("Tipo de gráfico no válido", "warning")
			return redirect(url_for("main.index"))
		
		if fig is None:
			flash("Error al generar el gráfico", "warning")
			return redirect(url_for("main.index"))
		
		# Aplicar tema oscuro
		fig = apply_dark_theme(fig)
		
		# Configurar kaleido antes de exportar
		try:
			# Intentar inicializar kaleido si no está inicializado
			if not hasattr(pio.kaleido.scope, '_initialized'):
				pio.kaleido.scope.default_format = "png"
				pio.kaleido.scope.default_width = 1200
				pio.kaleido.scope.default_height = 800
				pio.kaleido.scope.default_scale = 1
		except Exception as init_error:
			flash(f"Error al inicializar el exportador de imágenes: {str(init_error)}", "danger")
			return redirect(url_for("main.index"))
		
		# Exportar a PNG con timeout implícito
		try:
			# Usar to_image con configuración explícita
			img_bytes = pio.to_image(
				fig, 
				format="png", 
				engine="kaleido",
				width=1200,
				height=800,
				scale=1
			)
			
			if img_bytes is None:
				raise Exception("No se pudo generar la imagen")
			
			stream = BytesIO(img_bytes)
			stream.seek(0)
			
			flash(f"Gráfico {chart_type} exportado exitosamente", "success")
			return send_file(stream, as_attachment=True, download_name=filename, mimetype="image/png")
			
		except Exception as export_error:
			# Si falla kaleido, intentar con orca o mostrar mensaje de error
			error_msg = str(export_error)
			if "kaleido" in error_msg.lower() or "timeout" in error_msg.lower():
				flash("Error al exportar: El servicio de exportación de imágenes no está disponible. Por favor, intente nuevamente o use la función de captura de pantalla del navegador.", "warning")
			else:
				flash(f"Error al exportar gráfico: {error_msg}", "danger")
			return redirect(url_for("main.index"))
		
	except Exception as e:
		flash(f"Error al exportar gráfico: {str(e)}", "danger")
		return redirect(url_for("main.index"))
