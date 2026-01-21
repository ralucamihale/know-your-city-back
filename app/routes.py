from flask import Blueprint, request, jsonify
from .extensions import db
from .models import User, Grid, UnlockedCell
from werkzeug.security import generate_password_hash, check_password_hash
from geoalchemy2.elements import WKTElement
import jwt
import datetime
import math

main = Blueprint('main', __name__)
SECRET_KEY = "cheie_secreta_pentru_proiect_isi" # Schimbati in productie

# Task 2: Management utilizatori (Register/Login)
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
    
    # Returnam user_id SI is_admin
    token = jwt.encode({
        'user_id': str(user.id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, SECRET_KEY, algorithm="HS256")
    
    return jsonify({
        'token': token, 
        'user_id': str(user.id),
        'is_admin': user.is_admin  # <--- LINIA NOUA IMPORTANTA
    })

def write_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    try:
        with open("grid_log.txt", "a") as f:
            f.write(log_entry)
        print(log_entry.strip()) 
    except Exception as e:
        print(f"Eroare scriere log: {e}")

# ----------------------------------------

@main.route('/api/create_grid', methods=['POST'])
def create_game_grid():
    data = request.get_json()
    user_id = data.get('user_id')
    lat = data.get('lat')
    lng = data.get('lng')

    if not user_id or not lat or not lng:
        return jsonify({'message': 'Missing data'}), 400

    # 1. Check current grids to enforce limit
    existing_grids = Grid.query.filter_by(user_id=user_id).all()
    
    if len(existing_grids) >= 3:
        return jsonify({'message': 'Maximum limit reached (3/3). Delete a grid first.'}), 400

    # 2. Find the first empty slot (1, 2, or 3)
    occupied_slots = [g.slot_number for g in existing_grids]
    new_slot = next((i for i in range(1, 4) if i not in occupied_slots), None)

    if new_slot is None:
        return jsonify({'message': 'Error assigning slot'}), 400

    # 3. Create the new grid
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

    # Unlock start cell
    start_cell = UnlockedCell(grid_id=new_grid.id, row_index=0, col_index=0, message="Start Point")
    db.session.add(start_cell)
    
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

    # 1. Get center coordinates
    center_query = db.session.query(
        db.func.ST_X(grid.center_point), 
        db.func.ST_Y(grid.center_point)
    ).first()
    
    center_lng = center_query[0]
    center_lat = center_query[1]
    cell_size = grid.cell_size_meters

    # 2. Calculate distance in meters
    delta_lat_m = (user_lat - center_lat) * 111320
    delta_lng_m = (user_lng - center_lng) * (40075000 * math.cos(math.radians(center_lat)) / 360)

    # 3. Calculate Index
    row_idx = math.floor((delta_lat_m + (cell_size / 2)) / cell_size)
    col_idx = math.floor((delta_lng_m + (cell_size / 2)) / cell_size)

    # 4. Check bounds
    limit = grid.dimension // 2
    if abs(row_idx) > limit or abs(col_idx) > limit:
        return jsonify({'status': 'out_of_bounds', 'row': row_idx, 'col': col_idx})

    # 5. Save to DB
    existing = UnlockedCell.query.filter_by(grid_id=grid.id, row_index=row_idx, col_index=col_idx).first()
    
    if not existing:
        new_cell = UnlockedCell(grid_id=grid.id, row_index=row_idx, col_index=col_idx, message="Explored")
        db.session.add(new_cell)
        db.session.commit()
        return jsonify({'status': 'unlocked', 'row': row_idx, 'col': col_idx})
    
    return jsonify({'status': 'already_visited', 'row': row_idx, 'col': col_idx})

@main.route('/api/grid_data/<int:grid_id>', methods=['GET'])
def get_grid_data(grid_id):
    grid = Grid.query.get_or_404(grid_id)
        
    cells = UnlockedCell.query.filter_by(grid_id=grid.id).all()
    unlocked_data = [{'row': c.row_index, 'col': c.col_index} for c in cells]
    
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

@main.route('/api/grid/<int:grid_id>', methods=['GET'])
def get_grid_progress(grid_id):
    unlocked = UnlockedCell.query.filter_by(grid_id=grid_id).all()
    results = []
    for cell in unlocked:
        results.append({
            'row': cell.row_index,
            'col': cell.col_index,
            'msg': cell.message
        })
    return jsonify(results)

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

# --- RUTA NOUA PENTRU ADMIN ---
@main.route('/api/admin/all_grids', methods=['GET'])
def get_all_grids_admin():
    # Returnam TOATE grid-urile din baza de date, indiferent de user
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