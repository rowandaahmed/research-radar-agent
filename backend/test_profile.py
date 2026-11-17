from backend.profile_loader import load_professor_profile

profile = load_professor_profile("professor_001")

print("\n========== PROFESSOR PROFILE ==========\n")

print("Name:", profile["name"])
print("Institution:", profile["institution"])
print("Department:", profile["department"])

print("\nResearch Interests:")

for interest in profile["research_interests"]:
    print("-", interest)

print("\nResearch Goals:")

for goal in profile["research_goals"]:
    print("-", goal)