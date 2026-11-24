from flask import Flask, render_template, request, jsonify
import paramiko
import json
import shlex
from getpass import getpass 

app = Flask(__name__)

# SSH Configuration
SERVER = 'cuda01.imp.fu-berlin.de'
REMOTE_PORT = 22
USERNAME = None
PASSWORD = None
# Note: You can define your ZEDAT username and password here, so you won't have to put it in each time you restart the application. 
# Just remember to delete them when you share the code with others.


# Function to connect to the first server
def ssh_to_server(server_ip, username1, password1):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server_ip, username=username1, password=password1)
    return client


def execute_remote_command(command):
    """Connects to the remote server over SSH and executes a command."""
    try:
        # Connect to the server
        server_client = ssh_to_server(SERVER, USERNAME, PASSWORD)
        print("Connected to server")

        # Execute the command on the remote server
        stdin, stdout, stderr = server_client.exec_command(command)
        
        # Retrieve the output and error
        output = stdout.read().decode()
        error = stderr.read().decode()

        server_client.close()
        print("returning output\n")
        return {"output": output}
    except Exception as e:
        return {"error": str(e)}

# By default, the index page (templates/index.html) is displayed. Edit that page to customize your application.
@app.route('/')
def index():
    return render_template('index_triplanner.html')

@app.route('/add-column', methods=['POST'])
def add_column():
    data = request.json
    column_name = data.get('columnName', '')
    columns = data.get('columns', [])
    existing_rows = data.get('existingRows', [])

    prompt = f"""
    The user has a travel planning table with columns: {json.dumps(columns)}.
    Existing rows: {json.dumps(existing_rows)}
    Generate values for a new column called "{column_name}" for each existing row.
    Also generate 2 short action-oriented suggestions for this column (max 4 words each).
    Return ONLY valid JSON, no Markdown, no explanation.
    Format:
    {{"values": ["value1", "value2", "value3"], "suggestions": ["suggestion1", "suggestion2"]}}
    """

    payload = {
        "model": "llama3.1",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    payload_json = json.dumps(payload)
    escaped = shlex.quote(payload_json)
    curl_command = f"curl http://localhost:11434/api/chat -d {escaped}"
    result = execute_remote_command(curl_command)

    try:
        parsed = json.loads(result['output'])
        content = parsed['message']['content']
        values = json.loads(content)
        return jsonify(values)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add-row', methods=['POST'])
def add_row():
    data = request.json
    columns = data.get('columns', [])
    existing_rows = data.get('existingRows', [])

    prompt = f"""
    The user has a travel planning table with columns: {json.dumps(columns)}.
    Existing rows: {json.dumps(existing_rows)}
    Generate exactly 1 new travel suggestion row that is different from the existing ones.
    Return ONLY valid JSON, no Markdown, no explanation.
    Format:
    {{"values": ["value1", "value2", "value3"]}}
    """

    payload = {
        "model": "llama3.1",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    payload_json = json.dumps(payload)
    escaped = shlex.quote(payload_json)
    curl_command = f"curl http://localhost:11434/api/chat -d {escaped}"
    result = execute_remote_command(curl_command)

    try:
        parsed = json.loads(result['output'])
        content = parsed['message']['content']
        values = json.loads(content)
        return jsonify(values)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/refine-column', methods=['POST'])
def refine_column():
    data = request.json
    column = data.get('column', '')
    suggestion = data.get('suggestion', '')
    current_rows = data.get('rows', [])
    existing_rows = data.get('existingRows', [])

    prompt = f"""
    The user has a travel planning table.
    Column to refine: "{column}"
    Current values in this column: {json.dumps(current_rows)}
    Full table context - all columns and rows: {json.dumps(existing_rows)}
    Refine the values in the "{column}" column to match the style: "{suggestion}".
    Generate specific, concrete values based on each row's context.
    Return ONLY the raw JSON object, starting with {{ and ending with }}.
    Do not use code blocks, do not use backticks, do not add any text before or after.
    Format:
    {{"values": ["specific value for row 1", "specific value for row 2", "specific value for row 3"]}}
    """

    payload = {
        "model": "llama3.1",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    payload_json = json.dumps(payload)
    escaped = shlex.quote(payload_json)
    curl_command = f"curl http://localhost:11434/api/chat -d {escaped}"
    result = execute_remote_command(curl_command)

    try:
        parsed = json.loads(result['output'])
        content = parsed['message']['content']
        values = json.loads(content)
        return jsonify(values)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    prompt = data.get('prompt', '')
    system_prompt = """
        You are a professional aid in planning vacations/trips/activities. Your job is to help users plan their ideal vacation/trip/activity.

        The user wants to create a table outlining the vacation/trip/activity with fitting categories such as:
        time frame, destination, type of vacation (sportive/wellness), accommodation preferences,
        activities, budget, number of participants, dietary restrictions. 
        Please form your own categories and do not simply take the ones provided, 
        if other categories fit better.

        First, briefly summarize the user's request.

        Then generate concrete suggestions in table form (at least 3 rows)

        Adjust criteria based on user input.

        Do not deviate from the user's request unless asked.

        Provide links if possible.

        If no verified link exists, provide official website name + suggested search query.

        Always answer ONLY in valid JSON.

        Format:

        {
        "summary": "...",
        "columns": ["Column1", "Column2"],
        "rows": [
            ["value", "value"],
            ["value", "value"],
            ["value", "value"]
        ],
        "suggestions": {
            "Column1": ["Short suggestion A", "Short suggestion B"],
            "Column2": ["Short suggestion A", "Short suggestion B"]
        }
        }

        Generate a maximum of 4 travel suggestions.
        For suggestions: generate 2 short action-oriented suggestions per column (max 3 words each).
        The suggestions should
        Do not output Markdown.
        Do not output explanations.
        """

    payload = {
        "model": "llama3.1",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,

    }

    payload_json = json.dumps(payload)

    escaped = shlex.quote(payload_json)
    curl_command = f"curl http://localhost:11434/api/chat -d {escaped}"
    result = execute_remote_command(curl_command)
    #eingefügt:
    print("=== RAW RESULT ===")
    print(result)  # Zeigt ob SSH überhaupt funktioniert
    
    if 'error' in result:
        return jsonify({"error": result['error']}), 500
    
    print("=== RAW OUTPUT ===")
    print(result['output'])  # Zeigt was Ollama zurückgibt
    
    try:
        parsed_output = json.loads(result['output'])
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Ollama output not valid JSON: {str(e)}", "raw": result['output']}), 500
    
    content = parsed_output['message']['content']
    print("=== CONTENT ===")
    print(content)  # Zeigt was das Modell generiert hat
    
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Model content not valid JSON: {str(e)}", "raw": content}), 500
    
    return jsonify(parsed)

if __name__ == '__main__':
    if not PASSWORD or not USERNAME:
        USERNAME = input("Enter your username for the remote server: ")
        PASSWORD = getpass("Enter your password for the remote server: ")
    app.run()
