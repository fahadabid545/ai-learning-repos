# update_readme.py
import pandas as pd

def update_readme(csv_path="repos.csv", readme_path="README.md"):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"⚠️ {csv_path} not found, skipping README update.")
        return

    if df.empty:
        print("⚠️ CSV is empty, nothing to add to README.")
        return

    # Prepare columns
    df["Owner"] = df["full_name"].apply(lambda x: x.split("/")[0] if isinstance(x, str) else "")
    df["Repository"] = df.apply(lambda row: f"[{row['name']}]({row['url']})", axis=1)

    # Build markdown section per topic
    sections = []
    for topic, group in df.groupby("topic"):
        topic_df = group[["Repository", "Owner", "stars"]].rename(
            columns={"stars": "⭐ Stars"}
        ).sort_values(by="⭐ Stars", ascending=False)

        try:
            table_md = topic_df.to_markdown(index=False)  # needs tabulate
        except ImportError:
            # fallback: simple markdown table
            header = " | ".join(topic_df.columns)
            sep = " | ".join(["---"] * len(topic_df.columns))
            rows = "\n".join(" | ".join(map(str, row)) for row in topic_df.values)
            table_md = f"{header}\n{sep}\n{rows}"

        section = f"## {topic.capitalize()}\n\n{table_md}\n"
        sections.append(section)

    all_sections = "\n\n".join(sections)

    start = "<!-- REPO_TABLE_START -->"
    end = "<!-- REPO_TABLE_END -->"
    table_section = f"{start}\n\n{all_sections}\n\n{end}"

    # Read old README
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            readme = f.read()
    except FileNotFoundError:
        readme = "# Awesome AI Learning Repos\n\n"

    # Replace or append
    if start in readme and end in readme:
        before = readme.split(start)[0]
        after = readme.split(end)[1]
        new_readme = before + table_section + after
    else:
        new_readme = readme + "\n\n" + table_section

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)

    print(f"✅ Updated {readme_path} with latest repo tables by topic")


if __name__ == "__main__":
    update_readme()

