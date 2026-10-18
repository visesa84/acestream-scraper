from app.extensions import db
from sqlalchemy import event

class RecordingSchedule(db.Model):
    __tablename__ = 'recording_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('epg_programs.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    
    # Campos estáticos congelados para que la EPG no los sobrescriba
    title = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    
    retry_start = db.Column(db.DateTime, nullable=True)

    program = db.relationship('EPGProgram', backref=db.backref('recording_info', uselist=False))

# --- AUTOMATIZACIÓN ---
@event.listens_for(RecordingSchedule, 'before_insert')
def sync_data_from_program(mapper, connection, target):
    """Copia los tiempos y el título del EPGProgram en el momento de crear la programación"""
    if target.program_id:
        from app.models import EPGProgram  # Import local para evitar importación circular
        program = db.session.get(EPGProgram, target.program_id)
        if program:
            target.start_time = program.start_time
            target.end_time = program.end_time
            target.title = program.title
            target.description = program.description