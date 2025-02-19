from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
import requests
import threading
import time
import socket
import csv
import io

app = Flask(__name__)

# Initialize dictionaries to store progress and results
progress = {}
results_store = {}

def check_http_status_with_progress(hostnames, task_id):
    results = []
    total = len(hostnames)

    for i, hostname in enumerate(hostnames, start=1):
        hostname = hostname.strip()
        ips = []
        try:
            # Resolve hostname to IP addresses
            ips = socket.gethostbyname_ex(hostname)[-1]
        except socket.gaierror:
            ips = ['Unable to resolve']

        # Initialize variables to store status information
        status_http = None
        redirect_http = None
        title_http = None

        status_https = None
        redirect_https = None
        title_https = None

        # Try HTTP
        try:
            response_http = requests.get(f'http://{hostname}', allow_redirects=True, timeout=5)
            status_http = response_http.status_code
            redirect_http = response_http.url if response_http.history else None
            title_http = response_http.text.split('<title>')[1].split('</title>')[0] if '<title>' in response_http.text else 'N/A'
        except requests.RequestException:
            status_http = 'Error'

        # Try HTTPS
        try:
            response_https = requests.get(f'https://{hostname}', allow_redirects=True, timeout=5)
            status_https = response_https.status_code
            redirect_https = response_https.url if response_https.history else None
            title_https = response_https.text.split('<title>')[1].split('</title>')[0] if '<title>' in response_https.text else 'N/A'
        except requests.RequestException:
            status_https = 'Error'

        # Append the result for this hostname
        results.append({
            'hostname': hostname,
            'ips': ', '.join(ips),
            'status_http': status_http,
            'redirect_http': redirect_http,
            'title_http': title_http,
            'status_https': status_https,
            'redirect_https': redirect_https,
            'title_https': title_https
        })

        # Update progress
        progress[task_id] = (i / total) * 100

    # Once done, store the results
    results_store[task_id] = results
    progress[task_id] = 100  # Ensure progress is complete

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        hostnames = [line.decode('utf-8') for line in file.stream.readlines()]

        task_id = str(time.time())  # Create a unique task ID
        progress[task_id] = 0  # Initialize progress for this task

        # Start processing in a new thread
        thread = threading.Thread(target=check_http_status_with_progress, args=(hostnames, task_id))
        thread.start()

        return redirect(url_for('progress_view', task_id=task_id))

    return render_template('index.html')

@app.route('/progress/<task_id>', methods=['GET'])
def progress_view(task_id):
    return render_template('progress.html', task_id=task_id)

@app.route('/progress/<task_id>/status', methods=['GET'])
def get_progress(task_id):
    if task_id in progress:
        return jsonify({'progress': progress[task_id]})
    else:
        return jsonify({'error': 'Invalid task ID'}), 404

@app.route('/results/<task_id>', methods=['GET'])
def results(task_id):
    if task_id in results_store:
        return render_template('results.html', results=results_store[task_id], task_id=task_id)
    else:
        return "Results not found", 404

@app.route('/download/<task_id>', methods=['GET'])
def download_csv(task_id):
    if task_id not in results_store:
        return "Results not found", 404

    # Create a CSV in memory using BytesIO
    output = io.BytesIO()
    writer = csv.writer(output)
    writer.writerow(['Hostname', 'IP Addresses', 'HTTP Status', 'HTTP Redirect', 'HTTP Page Title',
                     'HTTPS Status', 'HTTPS Redirect', 'HTTPS Page Title'])

    for result in results_store[task_id]:
        writer.writerow([
            result['hostname'],
            result['ips'],
            result['status_http'],
            result['redirect_http'] or 'None',
            result['title_http'],
            result['status_https'],
            result['redirect_https'] or 'None',
            result['title_https']
        ])

    # Move the cursor to the beginning of the BytesIO object
    output.seek(0)

    # Return the file as a downloadable response
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='results.csv')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
