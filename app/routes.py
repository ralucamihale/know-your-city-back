from flask import Blueprint, request, jsonify
from .extensions import db
from .models import User, Grid, UnlockedCell
from werkzeug.security import generate_password_hash, check_password_hash
from geoalchemy2.elements import WKTElement
import jwt
import datetime
import math
from sqlalchemy import func

main = Blueprint('main', __name__)
SECRET_KEY = "cheie_secreta_pentru_proiect_isi" 

@main.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already exists'}), 400
        
    hashed_pw = generate_password_hash(data['password'])
    new_user = User(email=data['email'], password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'User created successfully'}), 201

@main.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'message': 'Login failed'}), 401
    
    token = jwt.encode({
        'user_id': str(user.id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, SECRET_KEY, algorithm="HS256")
    
    return jsonify({
        'token': token, 
        'user_id': str(user.id),
        'is_admin': user.is_admin
    })

@main.route('/api/create_grid', methods=['POST'])
def create_game_grid():
    data = request.get_json()
    user_id = data.get('user_id')
    lat = data.get('lat')
    lng = data.get('lng')

    if not user_id or not lat or not lng:
        return jsonify({'message': 'Missing data'}), 400

    existing_grids = Grid.query.filter_by(user_id=user_id).all()
    if len(existing_grids) >= 3:
        return jsonify({'message': 'Maximum limit reached (3/3). Delete a grid first.'}), 400

    occupied_slots = [g.slot_number for g in existing_grids]
    new_slot = next((i for i in range(1, 4) if i not in occupied_slots), None)

    if new_slot is None:
        return jsonify({'message': 'Error assigning slot'}), 400

    center_wkt = f'POINT({lng} {lat})'
    new_grid = Grid(
        user_id=user_id,
        name=f"Grid #{new_slot}",
        slot_number=new_slot,
        center_point=WKTElement(center_wkt, srid=4326),
        dimension=9,
        cell_size_meters=100
    )
    
    db.session.add(new_grid)
    db.session.commit()

    # Start cell
    start_cell = UnlockedCell(
        grid_id=new_grid.id, 
        row_index=0, 
        col_index=0, 
        message="Start Point",
        unlocked_at=datetime.datetime.now()
    )
    db.session.add(start_cell)
    db.session.commit()
    
    return jsonify({'message': 'Grid created!', 'grid_id': new_grid.id})

@main.route('/api/explore', methods=['POST'])
def explore_cell():
    data = request.get_json()
    user_lat = data.get('lat')
    user_lng = data.get('lng')
    user_id = data.get('user_id')
    grid_id = data.get('grid_id')
    
    if grid_id:
        grid = Grid.query.filter_by(id=grid_id, user_id=user_id).first()
    else:
        grid = Grid.query.filter_by(user_id=user_id).first()

    if not grid:
        return jsonify({'status': 'no_grid'})

    center_query = db.session.query(
        db.func.ST_X(grid.center_point), 
        db.func.ST_Y(grid.center_point)
    ).first()
    
    center_lng = center_query[0]
    center_lat = center_query[1]
    cell_size = grid.cell_size_meters

    delta_lat_m = (user_lat - center_lat) * 111320
    delta_lng_m = (user_lng - center_lng) * (40075000 * math.cos(math.radians(center_lat)) / 360)

    row_idx = math.floor((delta_lat_m + (cell_size / 2)) / cell_size)
    col_idx = math.floor((delta_lng_m + (cell_size / 2)) / cell_size)

    limit = grid.dimension // 2
    if abs(row_idx) > limit or abs(col_idx) > limit:
        return jsonify({'status': 'out_of_bounds', 'row': row_idx, 'col': col_idx})

    existing = UnlockedCell.query.filter_by(grid_id=grid.id, row_index=row_idx, col_index=col_idx).first()
    
    if not existing:
        now = datetime.datetime.now()
        new_cell = UnlockedCell(
            grid_id=grid.id, 
            row_index=row_idx, 
            col_index=col_idx, 
            message="Explored",
            unlocked_at=now
        )
        db.session.add(new_cell)
        db.session.commit()
        
        return jsonify({
            'status': 'unlocked', 
            'row': row_idx, 
            'col': col_idx,
            'time': now.strftime("%Y-%m-%d %H:%M") 
        })
    
    return jsonify({'status': 'already_visited', 'row': row_idx, 'col': col_idx})

@main.route('/api/grid_data/<int:grid_id>', methods=['GET'])
def get_grid_data(grid_id):
    grid = Grid.query.get_or_404(grid_id)
        
    cells = UnlockedCell.query.filter_by(grid_id=grid.id).all()
    
    unlocked_data = []
    for c in cells:
        time_str = c.unlocked_at.strftime("%Y-%m-%d %H:%M") if c.unlocked_at else "Unknown"
        unlocked_data.append({
            'row': c.row_index, 
            'col': c.col_index,
            'msg': c.message,
            'time': time_str
        })
    
    center_query = db.session.query(
        db.func.ST_X(grid.center_point), 
        db.func.ST_Y(grid.center_point)
    ).first()
    
    return jsonify({
        'has_grid': True,
        'grid_id': grid.id,
        'name': grid.name,
        'center_lat': center_query[1],
        'center_lng': center_query[0],
        'dimension': grid.dimension,
        'cell_size': grid.cell_size_meters,
        'unlocked_cells': unlocked_data
    })

@main.route('/api/user_grids/<user_id>', methods=['GET'])
def get_user_grids(user_id):
    grids = Grid.query.filter_by(user_id=user_id).order_by(Grid.created_at.desc()).all()
    results = []
    for g in grids:
        results.append({
            'id': g.id,
            'name': g.name,
            'slot': g.slot_number,
            'dimension': g.dimension,
            'created_at': g.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return jsonify(results)

@main.route('/api/delete_grid/<int:grid_id>', methods=['DELETE'])
def delete_grid(grid_id):
    grid = Grid.query.get(grid_id)
    if not grid:
        return jsonify({'message': 'Grid not found'}), 404

    UnlockedCell.query.filter_by(grid_id=grid.id).delete()
    user = User.query.get(grid.user_id)
    if user.active_grid_id == grid.id:
        user.active_grid_id = None

    db.session.delete(grid)
    db.session.commit()
    return jsonify({'message': 'Grid deleted successfully'})

@main.route('/api/admin/all_grids', methods=['GET'])
def get_all_grids_admin():
    grids = db.session.query(Grid, User.email).join(User, Grid.user_id == User.id).all()
    results = []
    for g, email in grids:
        results.append({
            'id': g.id,
            'name': f"{g.name} (by {email})",
            'slot': g.slot_number,
            'dimension': g.dimension,
            'created_at': g.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return jsonify(results)

# --- RUTA NOUA CARE LIPSEA ---
@main.route('/api/update_message', methods=['PUT'])
def update_message():
    data = request.get_json()
    user_id = data.get('user_id')
    grid_id = data.get('grid_id')
    row_idx = data.get('row')
    col_idx = data.get('col')
    new_message = data.get('message')

    # Verificari simple
    grid = Grid.query.filter_by(id=grid_id, user_id=user_id).first()
    if not grid:
        return jsonify({'error': 'Unauthorized'}), 403

    cell = UnlockedCell.query.filter_by(
        grid_id=grid.id, 
        row_index=row_idx, 
        col_index=col_idx
    ).first()

    if cell:
        cell.message = new_message
        db.session.commit()
        return jsonify({'message': 'Updated successfully', 'new_msg': new_message})
    
    return jsonify({'error': 'Cell not found'}), 404

# --- RUTA DASHBOARD STATS ---
@main.route('/api/stats', methods=['GET'])
def get_dashboard_stats():
    # 1. Statistici simple
    total_users = db.session.query(func.count(User.id)).scalar()
    total_grids = db.session.query(func.count(Grid.id)).scalar()
    total_cells = db.session.query(func.count(UnlockedCell.grid_id)).scalar()

    # 2. Statistici pentru Grafic (Ultimele 7 zile)
    # Group by date(unlocked_at)
    from datetime import timedelta
    
    seven_days_ago = datetime.datetime.now() - timedelta(days=7)
    
    # Query complex: Selecteaza data si numara celulele, grupate pe data
    results = db.session.query(
        func.date(UnlockedCell.unlocked_at), 
        func.count(UnlockedCell.grid_id)
    ).filter(
        UnlockedCell.unlocked_at >= seven_days_ago
    ).group_by(
        func.date(UnlockedCell.unlocked_at)
    ).all()
    
    # Formatam datele pentru Recharts (array de obiecte)
    chart_data = []
    for date_obj, count in results:
        chart_data.append({
            "date": date_obj.strftime('%Y-%m-%d'),
            "explored": count
        })
        
    # Sortam dupa data ca sa arate bine graficul
    chart_data.sort(key=lambda x: x['date'])

    return jsonify({
        'total_users': total_users,
        'total_grids': total_grids,
        'total_cells': total_cells,
        'chart_data': chart_data
    })