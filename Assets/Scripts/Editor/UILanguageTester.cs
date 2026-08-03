using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;
using System.Text;

public class UILanguageTester
{
    private string[] languages = { "en", "zh", "zh_long" };
    private Dictionary<string, List<UIIssue>> issuesByPrefab = new Dictionary<string, List<UIIssue>>();

    public void TestAllLanguages(List<string> prefabPaths, string outputFolder)
    {
        // 创建输出目录
        string timestamp = System.DateTime.Now.ToString("yyyy-MM-dd HH-mm-ss");
        string outputPath = Path.Combine(Application.dataPath, outputFolder, timestamp);
        Directory.CreateDirectory(outputPath);

        // 初始化LocalizationManager
        GameObject localizationManagerObj = new GameObject("LocalizationManager");
        LocalizationManager localizationManager = localizationManagerObj.AddComponent<LocalizationManager>();

        foreach (string prefabPath in prefabPaths)
        {
            issuesByPrefab[prefabPath] = new List<UIIssue>();

            foreach (string language in languages)
            {
                // 加载语言
                localizationManager.LoadLocalizedText(language);

                // 实例化预制体
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                if (prefab == null)
                    continue;

                GameObject instance = GameObject.Instantiate(prefab);
                instance.transform.position = Vector3.zero;

                // 更新所有LocalizedText组件
                LocalizedText[] localizedTexts = instance.GetComponentsInChildren<LocalizedText>(true);
                foreach (LocalizedText localizedText in localizedTexts)
                {
                    localizedText.UpdateText();
                }

                // 检测UI问题
                List<UIIssue> issues = DetectUIIssues(instance, language);
                issuesByPrefab[prefabPath].AddRange(issues);

                // 截图
                string prefabName = Path.GetFileNameWithoutExtension(prefabPath);
                string screenshotPath = Path.Combine(outputPath, $"{prefabName}_{language}.png");
                TakeScreenshot(screenshotPath);

                // 销毁实例
                GameObject.DestroyImmediate(instance);
            }
        }

        // 生成报告
        GenerateReport(outputPath);

        // 清理
        GameObject.DestroyImmediate(localizationManagerObj);

        EditorUtility.DisplayDialog("Test Complete", $"UI language test completed. Results saved to: {outputPath}", "OK");
    }

    private List<UIIssue> DetectUIIssues(GameObject instance, string language)
    {
        List<UIIssue> issues = new List<UIIssue>();

        // 检测文本超框
        UnityEngine.UI.Text[] texts = instance.GetComponentsInChildren<UnityEngine.UI.Text>(true);
        foreach (UnityEngine.UI.Text text in texts)
        {
            if (text.rectTransform != null)
            {
                float textWidth = text.preferredWidth;
                float rectWidth = text.rectTransform.rect.width;

                if (textWidth > rectWidth)
                {
                    issues.Add(new UIIssue
                    {
                        type = UIIssueType.TextOverflow,
                        description = $"Text overflow in {text.name}",
                        language = language
                    });
                }
            }
        }

        // 检测缺少翻译
        LocalizedText[] localizedTexts = instance.GetComponentsInChildren<LocalizedText>(true);
        foreach (LocalizedText localizedText in localizedTexts)
        {
            string key = localizedText.key;
            string value = LocalizationManager.Instance.GetLocalizedValue(key);

            if (value == key)
            {
                issues.Add(new UIIssue
                {
                    type = UIIssueType.MissingTranslation,
                    description = $"Missing translation for key: {key}",
                    language = language
                });
            }
        }

        // 检测UI元素重叠
        List<UnityEngine.UI.Graphic> graphics = new List<UnityEngine.UI.Graphic>();
        graphics.AddRange(instance.GetComponentsInChildren<UnityEngine.UI.Text>(true));
        graphics.AddRange(instance.GetComponentsInChildren<UnityEngine.UI.Image>(true));

        for (int i = 0; i < graphics.Count; i++)
        {
            for (int j = i + 1; j < graphics.Count; j++)
            {
                if (graphics[i] != null && graphics[j] != null &&
                    graphics[i].rectTransform != null && graphics[j].rectTransform != null)
                {
                    if (DoRectsOverlap(graphics[i].rectTransform.rect, graphics[j].rectTransform.rect))
                    {
                        issues.Add(new UIIssue
                        {
                            type = UIIssueType.ElementOverlap,
                            description = $"Overlap between {graphics[i].name} and {graphics[j].name}",
                            language = language
                        });
                    }
                }
            }
        }

        return issues;
    }

    private bool DoRectsOverlap(Rect rect1, Rect rect2)
    {
        return !(rect1.xMax < rect2.xMin || rect1.xMin > rect2.xMax ||
                 rect1.yMax < rect2.yMin || rect1.yMin > rect2.yMax);
    }

    private void TakeScreenshot(string path)
    {
        // 创建临时相机
        GameObject cameraObj = new GameObject("ScreenshotCamera");
        Camera camera = cameraObj.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = Color.white;
        camera.orthographic = true;
        camera.orthographicSize = 5;
        camera.transform.position = new Vector3(0, 0, -10);

        // 截图
        ScreenCapture.CaptureScreenshot(path);

        // 销毁相机
        GameObject.DestroyImmediate(cameraObj);
    }

    private void GenerateReport(string outputPath)
    {
        StringBuilder report = new StringBuilder();
        report.AppendLine("UI Language Test Report");
        report.AppendLine("=====================");
        report.AppendLine();

        foreach (KeyValuePair<string, List<UIIssue>> entry in issuesByPrefab)
        {
            string prefabPath = entry.Key;
            List<UIIssue> issues = entry.Value;

            report.AppendLine($"Prefab: {prefabPath}");
            report.AppendLine("Issues:");

            if (issues.Count == 0)
            {
                report.AppendLine("  - No issues found");
            }
            else
            {
                foreach (UIIssue issue in issues)
                {
                    report.AppendLine($"  - [{issue.language}] {issue.type}: {issue.description}");
                }
            }

            report.AppendLine();
        }

        string reportPath = Path.Combine(outputPath, "report.txt");
        File.WriteAllText(reportPath, report.ToString());
    }
}

public enum UIIssueType
{
    TextOverflow,
    MissingTranslation,
    ElementOverlap,
    TranslationError
}

public class UIIssue
{
    public UIIssueType type;
    public string description;
    public string language;
}
