import subprocess

def main():
    print("\n🌟 Starting local Streamlit App... 🌟\n")
    # Start the Streamlit app locally
    subprocess.run(["streamlit", "run", "app.py"])

if __name__ == "__main__":
    main()
