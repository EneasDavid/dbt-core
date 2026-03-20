#!/usr/bin/env python3

# Import the future annotations feature so the type hints stay lightweight.
from __future__ import annotations

# Import subprocess to execute the real terminal commands requested by the user.
import subprocess
# Import Path to resolve files relative to this script.
from pathlib import Path


# Resolve the dbt project root from the current script location.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Resolve the workspace root because the profile file lives one level above the dbt project.
WORKSPACE_ROOT = PROJECT_ROOT.parent
# Point to the project-local Python interpreter.
PYTHON_BIN = WORKSPACE_ROOT / ".venv" / "bin" / "python"
# Point to the dbt executable installed in the same virtual environment.
DBT_BIN = WORKSPACE_ROOT / ".venv" / "bin" / "dbt"
# Point to the output file that will keep the captured terminal transcript.
OUTPUT_PATH = PROJECT_ROOT / "analysis_outputs" / "out.txt"
# Point to the report generator script executed as part of the capture.
REPORT_SCRIPT = PROJECT_ROOT / "scripts" / "generate_iso_function_report.py"


# Run one terminal command and return a readable transcript section.
def run_command(title: str, command: list[str], cwd: Path) -> str:
    # Execute the command with stdout and stderr captured for the final transcript.
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    # Build a readable section header that explains what was run.
    lines = [f"=== {title} ===", ""]
    # Show the exact command line so the output can be reproduced manually.
    lines.append("$ " + " ".join(command))
    # Add an empty line before stdout for readability.
    lines.append("")
    # Label the stdout block explicitly.
    lines.append("--- STDOUT ---")
    # Include stdout or a placeholder when the command printed nothing.
    lines.append(completed.stdout.rstrip() or "(no stdout)")
    # Add a blank line before stderr.
    lines.append("")
    # Label the stderr block explicitly.
    lines.append("--- STDERR ---")
    # Include stderr or a placeholder when the command printed nothing.
    lines.append(completed.stderr.rstrip() or "(no stderr)")
    # Add a blank line before the exit code.
    lines.append("")
    # Record the exit code to prove whether the command succeeded.
    lines.append(f"--- EXIT CODE ---\n{completed.returncode}")
    # Add a final blank line so sections do not merge visually.
    lines.append("")
    # Return the formatted section text to the caller.
    return "\n".join(lines)


# Build the complete transcript from the small set of commands that matter for this assessment.
def build_transcript() -> str:
    # Define the ordered commands that prove environment, project connectivity, and ISO verdict output.
    command_specs = [
        ("DBT VERSION", [str(DBT_BIN), "--version"], WORKSPACE_ROOT),
        (
            "DBT DEBUG",
            [str(DBT_BIN), "debug", "--project-dir", str(PROJECT_ROOT), "--profiles-dir", str(WORKSPACE_ROOT)],
            WORKSPACE_ROOT,
        ),
        (
            "DBT PARSE",
            [str(DBT_BIN), "parse", "--project-dir", str(PROJECT_ROOT), "--profiles-dir", str(WORKSPACE_ROOT)],
            WORKSPACE_ROOT,
        ),
        ("ISO FUNCTION REPORT", [str(PYTHON_BIN), str(REPORT_SCRIPT)], WORKSPACE_ROOT),
    ]
    # Start the transcript with a short title block.
    sections = ["# Terminal transcript for the DBT Core ISO 19157 assessment", ""]
    # Run each command in order and append its captured section.
    for title, command, cwd in command_specs:
        sections.append(run_command(title, command, cwd))
    # Join every section into one final text blob.
    return "\n".join(sections)


# Write the transcript to disk and also print it to stdout.
def main() -> None:
    # Build the full command transcript.
    transcript = build_transcript()
    # Ensure the output directory exists before writing the file.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Save the transcript exactly as captured.
    OUTPUT_PATH.write_text(transcript, encoding="utf-8")
    # Print the transcript so the user can also see it in the terminal.
    print(transcript)
    # Print the output location as a final confirmation line.
    print(f"Transcript written to: {OUTPUT_PATH}")


# Execute the entrypoint only when the script is run directly.
if __name__ == "__main__":
    # Call the main function.
    main()
