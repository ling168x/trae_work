using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

public class UIPrefabScanner : EditorWindow
{
    private List<string> prefabPaths = new List<string>();
    private Vector2 scrollPosition;
    private string outputFolder = "UI_Scan_Results";

    [MenuItem("Tools/UI Prefab Scanner")]
    public static void ShowWindow()
    {
        GetWindow<UIPrefabScanner>("UI Prefab Scanner");
    }

    private void OnGUI()
    {
        GUILayout.Label("UI Prefab Scanner", EditorStyles.boldLabel);
        GUILayout.Space(10);

        if (GUILayout.Button("Scan for UI Prefabs"))
        {
            ScanPrefabs();
        }

        GUILayout.Space(10);
        GUILayout.Label("Found UI Prefabs:", EditorStyles.boldLabel);

        scrollPosition = GUILayout.BeginScrollView(scrollPosition);
        foreach (string path in prefabPaths)
        {
            GUILayout.Label(path);
        }
        GUILayout.EndScrollView();

        GUILayout.Space(10);
        outputFolder = EditorGUILayout.TextField("Output Folder:", outputFolder);

        if (GUILayout.Button("Start Language Test"))
        {
            StartLanguageTest();
        }
    }

    private void ScanPrefabs()
    {
        prefabPaths.Clear();
        string[] allPrefabs = Directory.GetFiles(Application.dataPath, "*.prefab", SearchOption.AllDirectories);

        foreach (string prefabPath in allPrefabs)
        {
            string relativePath = prefabPath.Replace(Application.dataPath, "Assets");
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(relativePath);
            if (prefab != null && HasUIElements(prefab))
            {
                prefabPaths.Add(relativePath);
            }
        }

        EditorUtility.DisplayDialog("Scan Complete", $"Found {prefabPaths.Count} UI prefabs", "OK");
    }

    private bool HasUIElements(GameObject prefab)
    {
        UnityEngine.UI.Text[] texts = prefab.GetComponentsInChildren<UnityEngine.UI.Text>(true);
        UnityEngine.UI.Button[] buttons = prefab.GetComponentsInChildren<UnityEngine.UI.Button>(true);
        UnityEngine.UI.Image[] images = prefab.GetComponentsInChildren<UnityEngine.UI.Image>(true);
        LocalizedText[] localizedTexts = prefab.GetComponentsInChildren<LocalizedText>(true);

        return texts.Length > 0 || buttons.Length > 0 || images.Length > 0 || localizedTexts.Length > 0;
    }

    private void StartLanguageTest()
    {
        if (prefabPaths.Count == 0)
        {
            EditorUtility.DisplayDialog("Error", "No UI prefabs found. Please scan first.", "OK");
            return;
        }

        UILanguageTester tester = new UILanguageTester();
        tester.TestAllLanguages(prefabPaths, outputFolder);
    }
}
