package com.example.gamebooster;

import android.content.Context;
import android.provider.Settings;
import android.util.Log;

import java.io.DataOutputStream;
import java.io.IOException;

public class GameSpeedController {

    private static final String TAG = "GameBooster";
    private Context context;
    private float speedMultiplier = 1.0f;
    private long originalTimeOffset = 0;
    private boolean isAccelerating = false;
    private Thread speedThread;
    private volatile boolean running = false;
    private boolean hasRoot = false;
    private Process suProcess = null;
    private DataOutputStream suOutputStream = null;
    private long lastTimeSet = 0;
    private static final long MIN_TIME_SET_INTERVAL = 2000;

    public GameSpeedController(Context context) {
        this.context = context;
    }

    public void setSpeed(float multiplier) {
        if (multiplier <= 0) {
            multiplier = 1.0f;
        }
        this.speedMultiplier = multiplier;
    }

    public float getSpeed() {
        return speedMultiplier;
    }

    public void startAcceleration() {
        if (isAccelerating) return;
        
        if (!Settings.System.canWrite(context)) {
            Log.e(TAG, "Cannot write to system settings");
            return;
        }

        if (!setupSuSession()) {
            Log.e(TAG, "Failed to setup SU session");
            return;
        }

        isAccelerating = true;
        running = true;
        originalTimeOffset = System.currentTimeMillis();
        lastTimeSet = originalTimeOffset;

        speedThread = new Thread(new Runnable() {
            @Override
            public void run() {
                while (running) {
                    try {
                        if (speedMultiplier != 1.0f && suOutputStream != null) {
                            long now = System.currentTimeMillis();
                            long elapsed = now - originalTimeOffset;
                            long acceleratedElapsed = (long) (elapsed * speedMultiplier);
                            long targetTime = originalTimeOffset + acceleratedElapsed;
                            long timeDiff = targetTime - now;
                            
                            if (timeDiff > 1000 && now - lastTimeSet >= MIN_TIME_SET_INTERVAL) {
                                setSystemTime(targetTime);
                                lastTimeSet = now;
                                Thread.sleep(1000);
                            } else {
                                Thread.sleep(100);
                            }
                        } else {
                            Thread.sleep(100);
                        }
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
        });
        speedThread.start();
    }

    private boolean setupSuSession() {
        if (suProcess != null) {
            return true;
        }

        try {
            suProcess = Runtime.getRuntime().exec("su");
            suOutputStream = new DataOutputStream(suProcess.getOutputStream());
            suOutputStream.writeBytes("echo 'SU session started'\n");
            suOutputStream.flush();
            
            new Thread(new Runnable() {
                @Override
                public void run() {
                    try {
                        suProcess.waitFor();
                        Log.d(TAG, "SU session ended");
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                }
            }).start();
            
            hasRoot = true;
            Log.d(TAG, "SU session established");
            return true;
        } catch (IOException e) {
            Log.e(TAG, "Failed to create SU process: " + e.getMessage());
            cleanupSuSession();
            return false;
        }
    }

    private void cleanupSuSession() {
        if (suOutputStream != null) {
            try {
                suOutputStream.writeBytes("exit\n");
                suOutputStream.flush();
                suOutputStream.close();
            } catch (IOException e) {
                Log.e(TAG, "Failed to close SU output stream: " + e.getMessage());
            }
            suOutputStream = null;
        }
        
        if (suProcess != null) {
            suProcess.destroy();
            suProcess = null;
        }
        
        hasRoot = false;
    }

    private void setSystemTime(long time) {
        if (suOutputStream == null) return;
        
        try {
            String timeStr = String.valueOf(time / 1000);
            suOutputStream.writeBytes("date -s @" + timeStr + "\n");
            suOutputStream.flush();
            Log.d(TAG, "Time set to: " + timeStr);
        } catch (IOException e) {
            Log.e(TAG, "Failed to set time: " + e.getMessage());
            cleanupSuSession();
        }
    }

    public void stopAcceleration() {
        running = false;
        isAccelerating = false;
        
        if (speedThread != null) {
            speedThread.interrupt();
            try {
                speedThread.join();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        
        syncNetworkTime();
        cleanupSuSession();
    }

    public boolean isAccelerating() {
        return isAccelerating;
    }

    private void syncNetworkTime() {
        if (suOutputStream != null) {
            try {
                suOutputStream.writeBytes("settings put global auto_time 1\n");
                suOutputStream.flush();
                Log.d(TAG, "Network time sync enabled");
            } catch (IOException e) {
                Log.e(TAG, "Failed to sync network time: " + e.getMessage());
            }
        }
    }
}