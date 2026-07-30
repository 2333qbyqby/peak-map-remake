using System;
using System.Collections.Generic;
using UnityEngine;

namespace VerticalIslandBaker.Editor
{
    [CreateAssetMenu(menuName = "Vertical Island Baker/Prefab Library")]
    public sealed class TerrainPrefabLibrary : ScriptableObject
    {
        [Serializable]
        public struct Binding
        {
            public string kind;
            public GameObject prefab;
        }

        public List<Binding> bindings = new();

        public GameObject Find(string kind)
        {
            foreach (Binding binding in bindings)
            {
                if (string.Equals(binding.kind, kind, StringComparison.OrdinalIgnoreCase))
                    return binding.prefab;
            }
            return null;
        }
    }
}

