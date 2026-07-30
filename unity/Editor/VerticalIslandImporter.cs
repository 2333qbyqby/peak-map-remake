using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace VerticalIslandBaker.Editor
{
    public sealed class VerticalIslandImporter : EditorWindow
    {
        [Serializable]
        private sealed class BakeConfig
        {
            public int resolution;
            public float world_size;
            public float world_height;
        }

        [Serializable]
        private sealed class SpawnObject
        {
            public string id;
            public string kind;
            public string category;
            public string biome;
            public float[] position;
            public float rotation_y;
            public float[] scale;
        }

        [Serializable]
        private sealed class SpawnManifest
        {
            public SpawnObject[] objects;
        }

        [SerializeField] private DefaultAsset bundleFolder;
        [SerializeField] private TerrainPrefabLibrary prefabLibrary;
        [SerializeField] private bool createPlaceholders = true;
        [SerializeField] private bool importSpawnObjects = true;

        [MenuItem("Tools/Vertical Island Baker/Import Bundle")]
        private static void Open() => GetWindow<VerticalIslandImporter>("Island Baker");

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Baked bundle", EditorStyles.boldLabel);
            bundleFolder = (DefaultAsset)EditorGUILayout.ObjectField(
                "Folder", bundleFolder, typeof(DefaultAsset), false);
            prefabLibrary = (TerrainPrefabLibrary)EditorGUILayout.ObjectField(
                "Prefab Library", prefabLibrary, typeof(TerrainPrefabLibrary), false);
            importSpawnObjects = EditorGUILayout.Toggle("Import Spawn Objects", importSpawnObjects);
            createPlaceholders = EditorGUILayout.Toggle("Create Missing Placeholders", createPlaceholders);

            using (new EditorGUI.DisabledScope(bundleFolder == null))
            {
                if (GUILayout.Button("Import Terrain"))
                    Import();
            }
        }

        private void Import()
        {
            string assetFolder = AssetDatabase.GetAssetPath(bundleFolder);
            string absoluteFolder = Path.GetFullPath(assetFolder);
            string configPath = Path.Combine(absoluteFolder, "config.json");
            string rawPath = Path.Combine(absoluteFolder, "height.raw");
            string manifestPath = Path.Combine(absoluteFolder, "spawn_manifest.json");

            if (!File.Exists(configPath) || !File.Exists(rawPath))
                throw new FileNotFoundException("Bundle must contain config.json and height.raw.");

            BakeConfig config = JsonUtility.FromJson<BakeConfig>(File.ReadAllText(configPath));
            byte[] bytes = File.ReadAllBytes(rawPath);
            int expected = config.resolution * config.resolution * sizeof(ushort);
            if (bytes.Length != expected)
                throw new InvalidDataException($"Expected {expected} raw bytes, got {bytes.Length}.");

            float[,] heights = new float[config.resolution, config.resolution];
            for (int row = 0; row < config.resolution; row++)
            {
                for (int col = 0; col < config.resolution; col++)
                {
                    int offset = (row * config.resolution + col) * 2;
                    ushort value = (ushort)(bytes[offset] | (bytes[offset + 1] << 8));
                    heights[row, col] = value / 65535f;
                }
            }

            TerrainData terrainData = new()
            {
                heightmapResolution = config.resolution,
                size = new Vector3(config.world_size, config.world_height, config.world_size)
            };
            terrainData.SetHeights(0, 0, heights);
            string dataPath = AssetDatabase.GenerateUniqueAssetPath(
                $"{assetFolder}/VerticalIslandTerrain.asset");
            AssetDatabase.CreateAsset(terrainData, dataPath);

            GameObject root = new("Vertical Island");
            Undo.RegisterCreatedObjectUndo(root, "Import vertical island");
            GameObject terrainObject = Terrain.CreateTerrainGameObject(terrainData);
            terrainObject.name = "Heightfield";
            terrainObject.transform.SetParent(root.transform);
            terrainObject.transform.position = new Vector3(
                -config.world_size * 0.5f, 0f, -config.world_size * 0.5f);

            if (importSpawnObjects && File.Exists(manifestPath))
                ImportObjects(root.transform, manifestPath);

            Selection.activeGameObject = root;
            AssetDatabase.SaveAssets();
        }

        private void ImportObjects(Transform parent, string manifestPath)
        {
            SpawnManifest manifest = JsonUtility.FromJson<SpawnManifest>(
                File.ReadAllText(manifestPath));
            if (manifest?.objects == null)
                return;

            GameObject objectRoot = new("Procedural Objects");
            objectRoot.transform.SetParent(parent);
            foreach (SpawnObject item in manifest.objects)
            {
                GameObject prefab = prefabLibrary != null ? prefabLibrary.Find(item.kind) : null;
                GameObject instance = prefab != null
                    ? (GameObject)PrefabUtility.InstantiatePrefab(prefab)
                    : CreatePlaceholder(item);
                if (instance == null)
                    continue;
                instance.name = $"{item.id}-{item.kind}";
                instance.transform.SetParent(objectRoot.transform);
                instance.transform.position = ToVector(item.position, Vector3.zero);
                instance.transform.rotation = Quaternion.Euler(0f, item.rotation_y, 0f);
                instance.transform.localScale = ToVector(item.scale, Vector3.one);
            }
        }

        private GameObject CreatePlaceholder(SpawnObject item)
        {
            if (!createPlaceholders)
                return null;
            PrimitiveType primitive = item.category == "vegetation"
                ? PrimitiveType.Cylinder
                : PrimitiveType.Sphere;
            return GameObject.CreatePrimitive(primitive);
        }

        private static Vector3 ToVector(float[] values, Vector3 fallback)
        {
            return values is { Length: >= 3 }
                ? new Vector3(values[0], values[1], values[2])
                : fallback;
        }
    }
}

