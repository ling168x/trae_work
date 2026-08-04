package com.example.gamebooster;

import android.util.Log;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

public class UnityHook {

    private static final String TAG = "GameBooster";
    private static float timeScale = 1.0f;
    private static boolean isHooked = false;

    public static void setTimeScale(float scale) {
        timeScale = scale;
        Log.d(TAG, "Set TimeScale: " + scale);
    }

    public static float getTimeScale() {
        return timeScale;
    }

    public static boolean hookUnityTime() {
        try {
            Class<?> unityPlayerClass = Class.forName("com.unity3d.player.UnityPlayer");
            Class<?> timeClass = findUnityTimeClass();
            
            if (timeClass != null) {
                hookTimeScale(timeClass);
                hookDeltaTime(timeClass);
                isHooked = true;
                Log.d(TAG, "Unity time hooks installed successfully");
                return true;
            } else {
                Log.e(TAG, "Unity Time class not found");
                return false;
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to hook Unity time: " + e.getMessage());
            return false;
        }
    }

    private static Class<?> findUnityTimeClass() {
        try {
            return Class.forName("UnityEngine.Time");
        } catch (ClassNotFoundException e) {
            try {
                return Class.forName("com.unity3d.player.UnityEngine.Time");
            } catch (ClassNotFoundException ex) {
                return null;
            }
        }
    }

    private static void hookTimeScale(Class<?> timeClass) throws Exception {
        try {
            Field timeScaleField = timeClass.getDeclaredField("timeScale");
            timeScaleField.setAccessible(true);
            
            Object originalValue = timeScaleField.get(null);
            if (originalValue instanceof Float) {
                timeScaleField.set(null, timeScale);
                Log.d(TAG, "Time.timeScale set to: " + timeScale);
            }
        } catch (NoSuchFieldException e) {
            try {
                Method setTimeScaleMethod = timeClass.getDeclaredMethod("set_timeScale", float.class);
                setTimeScaleMethod.invoke(null, timeScale);
                Log.d(TAG, "Time.timeScale set via method: " + timeScale);
            } catch (Exception ex) {
                Log.e(TAG, "Failed to set timeScale: " + ex.getMessage());
            }
        }
    }

    private static void hookDeltaTime(Class<?> timeClass) {
        try {
            Field deltaTimeField = timeClass.getDeclaredField("deltaTime");
            deltaTimeField.setAccessible(true);
            
            Object originalValue = deltaTimeField.get(null);
            if (originalValue instanceof Float) {
                float originalDelta = (Float) originalValue;
                float acceleratedDelta = originalDelta * timeScale;
                deltaTimeField.set(null, acceleratedDelta);
                Log.d(TAG, "DeltaTime accelerated: " + acceleratedDelta);
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to hook deltaTime: " + e.getMessage());
        }
    }

    public static void injectTimeScale(float scale) {
        timeScale = scale;
        
        if (isHooked) {
            try {
                Class<?> timeClass = findUnityTimeClass();
                if (timeClass != null) {
                    hookTimeScale(timeClass);
                }
            } catch (Exception e) {
                Log.e(TAG, "Failed to update timeScale: " + e.getMessage());
            }
        }
    }

    public static boolean isHooked() {
        return isHooked;
    }

    public static void startFrameHook() {
        new Thread(new Runnable() {
            @Override
            public void run() {
                while (true) {
                    try {
                        if (timeScale != 1.0f && isHooked) {
                            Class<?> timeClass = findUnityTimeClass();
                            if (timeClass != null) {
                                hookTimeScale(timeClass);
                            }
                        }
                        Thread.sleep(16);
                    } catch (Exception e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
        }).start();
    }
}