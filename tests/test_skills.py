from mgdvault.skills import iter_skill_dirs, read_description, skill_names


def test_bundled_skills_have_front_matter():
    assert skill_names() == ["mgdvault", "mgdvault-integration"]
    with iter_skill_dirs() as dirs:
        for d in dirs:
            text = (d / "SKILL.md").read_text()
            assert text.startswith("---\n")
            assert f"name: {d.name}" in text
            assert read_description(d)


def test_user_skill_forbids_printing_secrets():
    with iter_skill_dirs() as dirs:
        text = next(d for d in dirs if d.name == "mgdvault").joinpath("SKILL.md")
        assert "Never print a secret value" in text.read_text()
