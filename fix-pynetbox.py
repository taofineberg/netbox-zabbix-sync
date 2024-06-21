import os

def modify_query_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    with open(file_path, 'w') as file:
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip() == "if req.ok" and i + 1 < len(lines) and lines[i + 1].strip() == 'return req.headers.get("API-Version", "")':
                file.write('        if req.ok or req.status_code == 403:\n')
                file.write('            return req.headers.get("API-Version", "")\n')
                i += 2  # Skip the next line as it is already handled
            else:
                file.write(line)
                i += 1

def find_and_modify_query_file(start_dir):
    for root, dirs, files in os.walk(start_dir):
        if 'query.py' in files:
            file_path = os.path.join(root, 'query.py')
            modify_query_file(file_path)
            print(f"Modified file: {file_path}")
            return
    print("query.py file not found.")

if __name__ == "__main__":
    start_dir = os.getcwd()  # Start search in the current directory
    find_and_modify_query_file(start_dir)
