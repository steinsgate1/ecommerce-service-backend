from pathlib import Path


def load_prompt(name:str) -> str:
    path = Path(__file__).parent / "jinja2" / f"{name}.jinja2"
    return path.read_text(encoding="utf-8")

if __name__ == '__main__':
    print(load_prompt("chitchat"))