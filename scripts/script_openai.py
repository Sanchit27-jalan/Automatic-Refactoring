#!/usr/bin/env python3
import os
import random
import datetime
from github import Github
from openai import OpenAI

# OpenAI API endpoint and headers
def call_openai(prompt: str, role: str) -> str:
    """
    Calls the OpenAI API with the given prompt and role.
    """
    print(f"[OpenAI - {role}] Prompt (first 100 chars): {prompt[:100]}...\n")
    
    # Initialize the OpenAI client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENAI_KEY"],
    )
    
    # Create the API request
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",  # You can change this to another OpenAI model
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"{role}: {prompt}"},
        ]
    )
    
    # Extract and return the response content
    return response.choices[0].message.content

def get_repo() -> object:
    """
    Returns a PyGithub Repository object using the provided environment variables.
    """
    token = os.environ.get("TOKEN")
    repo_name = "Sanchit27-jalan/SE-Project-1"
    if not token or not repo_name:
        raise Exception("TOKEN and REPOSITORY must be set as environment variables.")
    
    g = Github(token)
    repo = g.get_repo(repo_name)
    print(f"Connected to GitHub repository: {repo_name}")
    return repo

def pick_files(repo, branch: str = "main", count: int = 2) -> list:
    """
    Retrieves the repository's file tree (recursively) from the specified branch,
    filters for Python files, randomly selects a directory, and randomly picks up to `count` files.
    """
    if branch is None:
        branch = repo.default_branch  # Use the default branch if none is provided
    
    tree = repo.get_git_tree(branch, recursive=True).tree
    
    # Group files by their parent directory
    dir_files = {}
    for item in tree:
        if item.type == "blob" and item.path.endswith(".java"):
            parent_dir = os.path.dirname(item.path)
            if parent_dir not in dir_files:
                dir_files[parent_dir] = []
            dir_files[parent_dir].append(item.path)
    
    # Randomly select a directory that has files
    if not dir_files:
        return []
    target_dir = random.choice(list(dir_files.keys()))
    
    # Select random files from target directory
    files_in_dir = dir_files[target_dir]
    selected_files = random.sample(files_in_dir, min(count, len(files_in_dir)))
    selected_files = ["reader-core/src/main/java/com/sismics/reader/core/dao/file/rss/RssReader.java", "reader-core/src/main/java/com/sismics/reader/core/service/FeedService.java"]
    print(f"Selected files from directory '{target_dir}':")
    for f in selected_files:
        print(" -", f)
    return selected_files

def refactor_file_with_llm(repo, file_path: str, branch: str, llm_callback, llm_name: str) -> (str, str):
    """
    Retrieves the file content from the repository, sends it to the specified LLM to detect design smells
    and generate a refactored version, and returns both the design smells summary and the new code.
    """
    content_file = repo.get_contents(file_path, ref=branch)
    original_code = content_file.decoded_content.decode('utf-8')
    
    prompt_design_smells = (
        f"Analyze the following code for design smells and code quality metrics including:"
        f"\n- Cyclomatic complexity"
        f"\n- Lines of code"
        f"\n- Method length"
        f"\n- Class coupling"
        f"\n- Number of parameters"
        f"\n- Depth of inheritance"
        f"\nList any issues found and provide recommendations for improvement:\n\n"
        f"{original_code}\n\n"
        "Please provide a brief summary focusing on the most critical issues and metrics that exceed common thresholds."
    )
    design_smells = llm_callback(prompt_design_smells, role="Design Smell Finder")
    
    prompt_refactor = (
        f"Based on the following detected design smells:\n{design_smells}\n\n"
        f"Refactor the code below to address these issues and improve code quality. "
        f"Return only the complete new file content:\n\n{original_code}"
    )
    refactored_code = llm_callback(prompt_refactor, role="Refactoring Expert")
    
    return design_smells, refactored_code, llm_name

def apply_refactorings_to_files(repo, files_updates: dict) -> str:
    """
    Creates a new branch from the main branch, updates the specified files with the new content,
    and commits the changes using the GitHub API.
    :param files_updates: A dict mapping file paths to their new content.
    :return: The name of the branch that was created.
    """
    # Create a new branch name based on the current timestamp.
    branch_name = "openai-refactor-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    ref_name = "refs/heads/" + branch_name

    # Get the latest commit sha from the main branch.
    main_branch = repo.get_branch("master")
    base_sha = main_branch.commit.sha

    print(f"Creating new branch '{branch_name}' from 'main'...")
    repo.create_git_ref(ref=ref_name, sha=base_sha)

    commit_message = "Apply OpenAI-suggested refactorings for selected files"
    # Update each file with the refactored content.
    for file_path, new_content in files_updates.items():
        print(f"Updating file: {file_path} at repo: {repo.full_name}")
        
        file_obj = repo.get_contents(file_path, ref=branch_name)
        repo.update_file(
            path=file_path,
            message=commit_message,
            content=new_content,
            sha=file_obj.sha,
            branch=branch_name
        )
    return branch_name

def create_pull_request(repo, branch_name: str, pr_body: str) -> str:
    """
    Creates a pull request against the original repository if working on a fork.
    :param repo: The repository object (which may be your fork).
    :param branch_name: The branch name where the changes are pushed.
    :param pr_body: The pull request description.
    :return: The URL of the created pull request.
    """
    # If working on a fork, use the parent (upstream) repository for the pull request.
    if repo.fork and repo.parent:
        target_repo = repo.parent
        head_branch = f"{repo.owner.login}:{branch_name}"
    else:
        target_repo = repo
        head_branch = branch_name

    title = "OpenAI Refactoring: Automated Code Improvements"
    base_branch = "master"
    pr = target_repo.create_pull(title=title, body=pr_body, head=head_branch, base=base_branch)
    return pr.html_url

def main():
    try:
        repo = get_repo()
        selected_files = pick_files(repo, branch="master", count=2)
        if not selected_files:
            print("No eligible files found for refactoring.")
            return
        
        files_design_smells = {}
        files_refactored = {}
        for file_path in selected_files:
            print(f"\nProcessing file: {file_path}")
            
            # Refactor with OpenAI
            openai_design_smells, openai_refactored_code, _ = refactor_file_with_llm(repo, file_path, "master", call_openai, "OpenAI")
            files_design_smells[f"{file_path}"] = openai_design_smells
            files_refactored[f"{file_path}"] = openai_refactored_code
        
        branch_name = apply_refactorings_to_files(repo, files_refactored)
        
        pr_body_lines = ["## OpenAI LLM Refactoring Summary\n"]
        for file_path, design_smells in files_design_smells.items():
            pr_body_lines.append(f"### File: `{file_path}`")
            pr_body_lines.append("**Design Smells Detected:**")
            pr_body_lines.append(design_smells)
            pr_body_lines.append("\n")
        pr_body = "\n".join(pr_body_lines)
        
        pr_url = create_pull_request(repo, branch_name, pr_body)
        print("\nPull Request created successfully:")
        print(pr_url)
    
    except Exception as e:
        print("An error occurred:", str(e))

if __name__ == "__main__":
    main()
