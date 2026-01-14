from flask import Blueprint, request, jsonify
from .extensions import db
from .models import User, Grid, UnlockedCell
from werkzeug.security import generate_password_hash, check_password_hash
from geoalchemy2.elements import WKTElement  # <--- IMPORT NOU
import jwt
import datetime
import math

main = Blueprint('main', __name__)
SECRET_KEY = "cheie_secreta_pentru_proiect_isi" # Schimbati in productie

# Task 2: Management utilizatori (Register/Login) [cite: 73]
@main.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already exists'}), 400
        
    hashed_pw = generate_password_hash(data['password'])
    new_user = User(email=data['email'], password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    
    # NOTA: Am scos crearea automata a grid-ului de aici.
    # Acum grid-ul se face manual prin butonul din aplicatie.

    return jsonify({'message': 'User created successfully'}), 201

@main.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'message': 'Login failed'}), 401
    
    # Returnam si user_id ca sa stie frontend-ul cine esti
    token = jwt.encode({
        'user_id': str(user.id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, SECRET_KEY, algorithm="HS256")
    
    return jsonify({'token': token, 'user_id': str(user.id)})

def write_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    try:
        with open("grid_log.txt", "a") as f:
            f.write(log_entry)
        print(log_entry.strip()) # Vedem și în consolă
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
    # If we have slots [1, 3], this logic finds 2.
    occupied_slots = [g.slot_number for g in existing_grids]
    new_slot = next((i for i in range(1, 4) if i not in occupied_slots), None)

    if new_slot is None:
        return jsonify({'message': 'Error assigning slot'}), 400

    # 3. Create the new grid
    center_wkt = f'POINT({lng} {lat})'
    new_grid = Grid(
        user_id=user_id,
        name=f"Grid #{new_slot}",
        slot_number=new_slot, # Ensures we fit inside the Check Constraint
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
    grid_id = data.get('grid_id') # <--- NEW PARAMETER
    
    # FIX: Find the SPECIFIC grid by ID, not just any grid belonging to the user
    if grid_id:
        grid = Grid.query.filter_by(id=grid_id, user_id=user_id).first()
    else:
        # Fallback for old code (optional)
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
        
    # Get unlocked cells
    cells = UnlockedCell.query.filter_by(grid_id=grid.id).all()
    unlocked_data = [{'row': c.row_index, 'col': c.col_index} for c in cells]
    
    # Get center coordinates
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

# Task 3 & 7: Logică spațială și returnare date grid [cite: 74, 78]
@main.route('/api/grid/<int:grid_id>', methods=['GET'])
def get_grid_progress(grid_id):
    # Returnăm celulele deblocate pentru a fi desenate pe hartă
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

    # 1. Delete dependent cells first (Foreign Key Fix)
    UnlockedCell.query.filter_by(grid_id=grid.id).delete()

    # 2. Update user if this was their "active" grid
    user = User.query.get(grid.user_id)
    if user.active_grid_id == grid.id:
        user.active_grid_id = None

    # 3. Delete the grid
    db.session.delete(grid)
    db.session.commit()

    return jsonify({'message': 'Grid deleted successfully'})