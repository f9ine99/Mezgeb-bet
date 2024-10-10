from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = '33122110@33122110'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Hardcoded credentials
workers = {

    "Nuguse": "password1",
    "Teshager": "password2",
    "Imebet": "password3",
    "Olana": "password4",
    "Gezahegn": "password5",
    "Bereket": "password6",
    "Hirut": "password7",
}

providers = {
    "Leelloo": "providerpassword1",
    "Gonfa": "providerpassword2",
}

admins = {
    "admin": "adminpassword",
}

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_role = db.Column(db.String(20), nullable=False) 
    username = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    client_id = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"<ActivityLog {self.id} - {self.action} by {self.username}>"

class Request(db.Model):
    request_id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.String(50), nullable=False)  # Current worker
    client_id = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    provider_id = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Transfer tracking
    transferred_by = db.Column(db.String(50), nullable=True)  # Worker who transferred the request
    transferred_to = db.Column(db.String(50), nullable=True)  # New worker receiving the request
    transfer_timestamp = db.Column(db.DateTime, nullable=True)  # Time of transfer
    transfer_comment = db.Column(db.Text, nullable=True)  # Comment added during transfer


class Transfer(db.Model):
    transfer_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('request.request_id'), nullable=False)
    transferred_by = db.Column(db.String(50), nullable=False)
    transferred_to = db.Column(db.String(50), nullable=False)
    transfer_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    transfer_comment = db.Column(db.Text, nullable=True)

    request = db.relationship('Request', backref=db.backref('transfers', lazy=True))

    def __repr__(self):
        return f"<Transfer {self.transfer_id} - Request {self.request_id}>"


# Create database tables
with app.app_context():
    db.create_all()



def log_activity(user_role, username, action, details=None):
    activity = ActivityLog(
        user_role=user_role,
        username=username,
        action=action,
        details=details
    )
    db.session.add(activity)
    db.session.commit()


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form  # Check if "Remember Me" was selected

        if username in workers and workers[username] == password:
            session['worker_id'] = username
            if remember:
                session.permanent = True  # Set session to permanent if "Remember Me" is checked
                app.permanent_session_lifetime = timedelta(days=7)  # Session lasts for 7 days
            return redirect(url_for('worker_dashboard'))
        elif username in providers and providers[username] == password:
            session['provider_id'] = username
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=7)
            return redirect(url_for('provider_dashboard'))
        elif username in admins and admins[username] == password:
            session['admin_id'] = username
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=7)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials, please try again.')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# Worker Request Form
@app.route('/request_clients', methods=['GET', 'POST'])
def request_clients():
    if request.method == 'POST':
        worker_id = session.get('worker_id')
        if not worker_id:
            flash('You need to log in first.')
            return redirect(url_for('login'))

        client_ids_str = request.form['client_ids']
        client_ids = [client_id.strip() for client_id in client_ids_str.split(',')]

        for client_id in client_ids:
            new_request = Request(
                worker_id=worker_id,
                client_id=client_id,
                status='Pending',
                timestamp=datetime.now()
            )
            db.session.add(new_request)
        db.session.commit()

        log_activity(
            user_role='worker',
            username=worker_id,
            action='Requested Client Data',
            details=f"Requested Client IDs: {', '.join(client_ids)}"
        )

        flash('Client requests submitted successfully.')
        return redirect(url_for('worker_dashboard'))

    return render_template('request_clients.html')

####

@app.route('/provider_dashboard', methods=['GET', 'POST'])
def provider_dashboard():
    if 'provider_id' not in session:
        flash('You need to log in as a provider first.')
        return redirect(url_for('login'))

    provider_id = session['provider_id']

    # Get the current page from the query string, default to 1 if not set
    page = request.args.get('page', 1, type=int)
    
    if request.method == 'POST':
        request_id = request.form['request_id']  
        status = request.form['status'] 

        request_entry = Request.query.get(request_id)
        if request_entry:
            previous_status = request_entry.status
            request_entry.status = status
            request_entry.provider_id = provider_id  
            request_entry.timestamp = datetime.now()
            db.session.commit()

            # Log the status update
            log_activity(
                user_role='provider',
                username=provider_id,
                action='Updated Request Status',
                details=f"Request ID: {request_id}, Previous Status: {previous_status}, New Status: {status}"
            )

            flash('Request updated successfully.')
        else:
            flash('Request not found.')

        return redirect(url_for('provider_dashboard'))

    # Paginate the request list: per page is 10, and the current page is 'page'
    requests = Request.query.paginate(page=page, per_page=10, error_out=False)
    return render_template('provider_dashboard.html', requests=requests)



# Worker Dashboard
@app.route('/worker_dashboard')
def worker_dashboard():
    if 'worker_id' not in session:
        flash('You need to log in first.')
        return redirect(url_for('login'))

    worker_id = session['worker_id']

    # Fetch all requests associated with the worker (either owned or transferred to them)
    requests = Request.query.filter(
        (Request.worker_id == worker_id) | (Request.transferred_to == worker_id)
    ).all()

    # Calculate Quick Stats
    total_requests = Request.query.filter(
        (Request.worker_id == worker_id) | (Request.transferred_to == worker_id)
    ).count()

    pending_requests = Request.query.filter(
        (Request.worker_id == worker_id) | (Request.transferred_to == worker_id),
        Request.status == 'Pending'
    ).count()

    approved_requests = Request.query.filter(
        (Request.worker_id == worker_id) | (Request.transferred_to == worker_id),
        Request.status == 'Approved'
    ).count()

    confirmed_deliveries = Request.query.filter(
        (Request.worker_id == worker_id) | (Request.transferred_to == worker_id),
        Request.status == 'Confirmed'
    ).count()

    # Attach transfer history to each request
    for req in requests:
        req.transfers = Transfer.query.filter_by(request_id=req.request_id).all()

    # Debugging lines to verify counts (check your console)
    print(f"Total Requests: {total_requests}")
    print(f"Pending Requests: {pending_requests}")
    print(f"Approved Requests: {approved_requests}")
    print(f"Confirmed Deliveries: {confirmed_deliveries}")

    return render_template(
        'worker_dashboard.html',
        requests=requests,
        total_requests=total_requests,
        pending_requests=pending_requests,
        approved_requests=approved_requests,
        confirmed_deliveries=confirmed_deliveries
    )

###########

from datetime import datetime, timedelta

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin_id' not in session:
        flash('You need to log in as an admin first.')
        return redirect(url_for('login'))

    # Pagination settings
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Retrieve filter parameters from query string
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    user_role = request.args.get('user_role', '')
    username = request.args.get('username', '')
    action_type = request.args.get('action_type', '')
    filter_type = request.args.get('filter', '')  # For daily activity filter
    client_id = request.args.get('client_id', '')  # New filter parameter

    # Build the query
    query = ActivityLog.query

    # Filter for today's activity if 'daily_activity' is selected
    if filter_type == 'daily_activity':
        today = datetime.now().date()  # Get today's date (YYYY-MM-DD)
        tomorrow = today + timedelta(days=1)  # Start of tomorrow (YYYY-MM-DD)
        today_start = datetime.combine(today, datetime.min.time())  # Start of today (00:00:00)
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time())  # Start of tomorrow (00:00:00)
        query = query.filter(ActivityLog.timestamp >= today_start).filter(ActivityLog.timestamp < tomorrow_start)

    # Filter by date range if provided
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(ActivityLog.timestamp >= start_date)
        except ValueError:
            flash("Invalid start date format.")
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(ActivityLog.timestamp <= end_date)
        except ValueError:
            flash("Invalid end date format.")

    # Filter by user role
    if user_role:
        query = query.filter(ActivityLog.user_role.ilike(f"%{user_role}%"))
    
    # Filter by username
    if username:
        query = query.filter(ActivityLog.username.ilike(f"%{username}%"))

    # Filter by action type
    if action_type:
        query = query.filter(ActivityLog.action.ilike(f"%{action_type}%"))
    
    # Filter by client_id (new functionality)
    if client_id:
        query = query.filter(ActivityLog.client_id.ilike(f"%{client_id}%"))

    # Apply pagination
    transfers = query.order_by(ActivityLog.timestamp.desc()).paginate(page=page, per_page=per_page)

    return render_template(
        'admin_dashboard.html',
        transfers=transfers.items,
        pagination=transfers,
        start_date=start_date,
        end_date=end_date,
        user_role=user_role,
        username=username,
        action_type=action_type,
        filter_type=filter_type,
        client_id=client_id  # Pass the client_id filter value to the template
    )



#######


@app.route('/transfer_request/<int:request_id>', methods=['GET', 'POST'])
def transfer_request(request_id):
    if 'worker_id' not in session:
        flash('You need to log in first.')
        return redirect(url_for('login'))

    current_worker = session['worker_id']
    request_entry = Request.query.get_or_404(request_id)

    # Ensure the current worker owns the request or has the authority to transfer it
    if request_entry.worker_id != current_worker and request_entry.transferred_to != current_worker:
        flash('You do not have permission to transfer this request.')
        return redirect(url_for('worker_dashboard'))

    if request.method == 'POST':
        target_worker = request.form['target_worker']
        comment = request.form.get('comment', '')

        if target_worker not in workers:
            flash('Selected worker does not exist.')
            return redirect(url_for('transfer_request', request_id=request_id))

        # Update the request with transfer details
        request_entry.transferred_by = current_worker
        request_entry.transferred_to = target_worker
        request_entry.transfer_timestamp = datetime.now()
        request_entry.transfer_comment = comment
        request_entry.worker_id = target_worker  # Assign the request to the new worker

        # Create a new Transfer record
        new_transfer = Transfer(
            request_id=request_id,
            transferred_by=current_worker,
            transferred_to=target_worker,
            transfer_timestamp=datetime.now(),
            transfer_comment=comment
        )
        db.session.add(new_transfer)

        # Commit both the request update and the transfer record
        db.session.commit()

        # Log the transfer activity
        log_activity(
            user_role='worker',
            username=current_worker,
            action='Transferred Request',
            details=f"Request ID: {request_id}, Transferred To: {target_worker}, Comment: {comment}"
        )

        flash(f'Request {request_id} has been transferred to {target_worker}.')
        return redirect(url_for('worker_dashboard'))

    # Exclude current worker from the list of target workers
    available_workers = [w for w in workers.keys() if w != current_worker]

    return render_template('transfer_request.html', request=request_entry, available_workers=available_workers)





# Worker Confirmation of Delivered Data
@app.route('/confirm_delivery', methods=['POST'])
def confirm_delivery():
    request_ids = request.form.getlist('request_ids')
    worker_id = session.get('worker_id')

    if not worker_id:
        flash('You need to log in first.')
        return redirect(url_for('login'))

    for request_id in request_ids:
        request_entry = Request.query.get(request_id)
        if request_entry and request_entry.status == 'Approved':
            request_entry.status = 'Confirmed'
            request_entry.timestamp = datetime.now()
            db.session.commit()

            # Log the delivery confirmation
            log_activity(
                user_role='worker',
                username=worker_id,
                action='Confirmed Delivery',
                details=f"Request ID: {request_id}"
            )

    flash('Data confirmed as delivered successfully.')
    return redirect(url_for('worker_dashboard'))



@app.route('/routes')
def list_routes():
    import urllib
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        line = urllib.parse.unquote(f"{rule.endpoint:50s} {methods:20s} {rule}")
        output.append(line)
    return '<br>'.join(output)


# Run the application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)