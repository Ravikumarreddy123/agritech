import kagglehub

# Download latest version of PlantVillage dataset
path = kagglehub.dataset_download("emmarex/plantdisease")

print("✅ Dataset downloaded successfully!")
print("📂 Path to dataset files:", path)
