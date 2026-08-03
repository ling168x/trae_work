using UnityEngine;
using System.Collections.Generic;
using System.IO;

public class LocalizationManager : MonoBehaviour
{
    public static LocalizationManager Instance { get; private set; }
    private Dictionary<string, Dictionary<string, string>> localizedText = new Dictionary<string, Dictionary<string, string>>();
    private string currentLanguage = "en";

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        else
        {
            Destroy(gameObject);
        }
    }

    public void LoadLocalizedText(string languageCode)
    {
        currentLanguage = languageCode;
        string filePath = Path.Combine(Application.streamingAssetsPath, $"Localization/{languageCode}.json");

        if (File.Exists(filePath))
        {
            string dataAsJson = File.ReadAllText(filePath);
            LocalizationData loadedData = JsonUtility.FromJson<LocalizationData>(dataAsJson);

            if (!localizedText.ContainsKey(languageCode))
            {
                localizedText[languageCode] = new Dictionary<string, string>();
            }

            foreach (LocalizationItem item in loadedData.items)
            {
                localizedText[languageCode][item.key] = item.value;
            }
        }
        else
        {
            Debug.LogError($"Cannot find localization file for language: {languageCode}");
        }
    }

    public string GetLocalizedValue(string key)
    {
        if (localizedText.ContainsKey(currentLanguage) && localizedText[currentLanguage].ContainsKey(key))
        {
            return localizedText[currentLanguage][key];
        }
        return key;
    }

    public void ChangeLanguage(string languageCode)
    {
        LoadLocalizedText(languageCode);
        // 通知所有UI元素更新文本
        UnityEngine.Events.UnityEvent languageChangedEvent = new UnityEngine.Events.UnityEvent();
        languageChangedEvent.Invoke();
    }

    public string[] GetAvailableLanguages()
    {
        string localizationFolder = Path.Combine(Application.streamingAssetsPath, "Localization");
        if (Directory.Exists(localizationFolder))
        {
            string[] files = Directory.GetFiles(localizationFolder, "*.json");
            List<string> languages = new List<string>();
            foreach (string file in files)
            {
                languages.Add(Path.GetFileNameWithoutExtension(file));
            }
            return languages.ToArray();
        }
        return new string[] { "en" };
    }
}

[System.Serializable]
public class LocalizationData
{
    public LocalizationItem[] items;
}

[System.Serializable]
public class LocalizationItem
{
    public string key;
    public string value;
}
