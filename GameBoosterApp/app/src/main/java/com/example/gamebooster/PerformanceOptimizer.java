package com.example.gamebooster;

import android.content.Context;
import android.os.Build;
import android.util.Log;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;

public class PerformanceOptimizer {

    private static final String TAG = "GameBooster";
    private Context context;
    private boolean isOptimizing = false;

    public PerformanceOptimizer(Context context) {
        this.context = context;
    }

    public void startOptimization(int level) {
        if (isOptimizing) return;
        isOptimizing = true;

        try {
            optimizeCPU(level);
        } catch (Exception e) {
            Log.e(TAG, "CPU optimization skipped (requires root)", e);
        }

        try {
            optimizeGPU();
        } catch (Exception e) {
            Log.e(TAG, "GPU optimization skipped (requires root)", e);
        }

        try {
            optimizeMemory();
        } catch (Exception e) {
            Log.e(TAG, "Memory optimization failed", e);
        }

        try {
            optimizeNetwork();
        } catch (Exception e) {
            Log.e(TAG, "Network optimization skipped", e);
        }
        
        try {
            setProcessPriority();
        } catch (Exception e) {
            Log.e(TAG, "Priority setting failed", e);
        }

        Log.i(TAG, "Optimization started with level: " + level);
    }

    public void stopOptimization() {
        if (!isOptimizing) return;
        isOptimizing = false;
        
        try {
            restoreDefaultSettings();
        } catch (Exception e) {
            Log.e(TAG, "Restore failed", e);
        }
        
        Log.i(TAG, "Optimization stopped");
    }

    public void optimizeCPU(int level) {
        if (!hasRootAccess()) {
            Log.w(TAG, "Root access not available, CPU optimization skipped");
            return;
        }

        try {
            File governorFile = new File("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor");
            if (governorFile.exists()) {
                String cpuGovernor = getCurrentCPUGovernor();
                Log.d(TAG, "Current CPU Governor: " + cpuGovernor);

                if (level >= 2) {
                    setCPUGovernor("performance");
                } else if (level == 1) {
                    setCPUGovernor("interactive");
                }
            } else {
                Log.w(TAG, "CPU governor file not found");
            }

            setCPUFrequency(level);
        } catch (Exception e) {
            Log.e(TAG, "CPU optimization failed", e);
        }
    }

    public void optimizeCPU() {
        optimizeCPU(3);
    }

    public void optimizeGPU() {
        if (!hasRootAccess()) {
            Log.w(TAG, "Root access not available, GPU optimization skipped");
            return;
        }

        try {
            writeToFile("/sys/class/kgsl/kgsl-3d0/max_gpuclk", "600000000");
            writeToFile("/sys/class/kgsl/kgsl-3d0/pwrscale/trustzone/enable", "1");
        } catch (Exception e) {
            Log.e(TAG, "GPU optimization failed", e);
        }
    }

    public void optimizeMemory() {
        try {
            Runtime.getRuntime().gc();
            trimMemory();
        } catch (Exception e) {
            Log.e(TAG, "Memory optimization failed", e);
        }
    }

    public void cleanMemory() {
        optimizeMemory();
    }

    public void optimizeNetwork() {
        if (!hasRootAccess()) {
            Log.w(TAG, "Root access not available, network optimization skipped");
            return;
        }

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                android.net.ConnectivityManager cm = 
                    (android.net.ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
                if (cm != null) {
                    cm.setProcessDefaultNetwork(null);
                }
            }
            writeToFile("/proc/sys/net/ipv4/tcp_timestamps", "1");
            writeToFile("/proc/sys/net/ipv4/tcp_sack", "1");
            writeToFile("/proc/sys/net/ipv4/tcp_window_scaling", "1");
        } catch (Exception e) {
            Log.e(TAG, "Network optimization failed", e);
        }
    }

    private boolean hasRootAccess() {
        try {
            Process process = Runtime.getRuntime().exec("su -c id");
            int exitCode = process.waitFor();
            return exitCode == 0;
        } catch (Exception e) {
            return false;
        }
    }

    private void setCPUFrequency(int level) {
        try {
            File cpuDir = new File("/sys/devices/system/cpu/");
            File[] cpuFiles = cpuDir.listFiles();
            
            if (cpuFiles != null) {
                for (File cpuFile : cpuFiles) {
                    if (cpuFile.getName().startsWith("cpu")) {
                        String maxFreqPath = cpuFile.getAbsolutePath() + "/cpufreq/scaling_max_freq";
                        String minFreqPath = cpuFile.getAbsolutePath() + "/cpufreq/scaling_min_freq";
                        
                        String maxFreq, minFreq;
                        if (level == 3) {
                            maxFreq = getMaxFrequency(cpuFile.getName());
                            minFreq = "1000000";
                        } else if (level == 2) {
                            maxFreq = getMaxFrequency(cpuFile.getName());
                            minFreq = "500000";
                        } else {
                            maxFreq = "1500000";
                            minFreq = "200000";
                        }
                        
                        writeToFile(maxFreqPath, maxFreq);
                        writeToFile(minFreqPath, minFreq);
                    }
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "CPU frequency setting failed", e);
        }
    }

    private String getMaxFrequency(String cpuName) {
        try {
            String path = "/sys/devices/system/cpu/" + cpuName + "/cpufreq/cpuinfo_max_freq";
            return readFile(path);
        } catch (Exception e) {
            return "2000000";
        }
    }

    private String getCurrentCPUGovernor() {
        try {
            return readFile("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor");
        } catch (Exception e) {
            return "unknown";
        }
    }

    private void setCPUGovernor(String governor) {
        try {
            File cpuDir = new File("/sys/devices/system/cpu/");
            File[] cpuFiles = cpuDir.listFiles();
            
            if (cpuFiles != null) {
                for (File cpuFile : cpuFiles) {
                    if (cpuFile.getName().startsWith("cpu")) {
                        String path = cpuFile.getAbsolutePath() + "/cpufreq/scaling_governor";
                        writeToFile(path, governor);
                    }
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "CPU governor setting failed", e);
        }
    }

    private void setProcessPriority() {
        try {
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_URGENT_DISPLAY);
        } catch (Exception e) {
            Log.e(TAG, "Priority setting failed", e);
        }
    }

    private void trimMemory() {
        try {
            Runtime runtime = Runtime.getRuntime();
            long usedBefore = runtime.totalMemory() - runtime.freeMemory();
            runtime.gc();
            long usedAfter = runtime.totalMemory() - runtime.freeMemory();
            Log.d(TAG, "Memory cleaned: " + (usedBefore - usedAfter) / 1024 + " KB");
        } catch (Exception e) {
            Log.e(TAG, "Memory trim failed", e);
        }
    }

    private void restoreDefaultSettings() {
        if (!hasRootAccess()) {
            Log.w(TAG, "Root access not available, restore skipped");
            return;
        }

        try {
            setCPUGovernor("schedutil");
            writeToFile("/proc/sys/net/ipv4/tcp_timestamps", "0");
        } catch (Exception e) {
            Log.e(TAG, "Restore failed", e);
        }
    }

    private void writeToFile(String path, String value) {
        try {
            String command = "echo '" + value + "' > " + path;
            Process process = Runtime.getRuntime().exec(new String[]{"su", "-c", command});
            int exitCode = process.waitFor();
            if (exitCode != 0) {
                Log.d(TAG, "Command failed with exit code: " + exitCode);
            }
        } catch (Exception e) {
            Log.d(TAG, "Cannot write to " + path + ": " + e.getMessage());
        }
    }

    private String readFile(String path) throws Exception {
        FileInputStream fis = new FileInputStream(path);
        BufferedReader reader = new BufferedReader(new InputStreamReader(fis));
        String result = reader.readLine();
        reader.close();
        fis.close();
        return result != null ? result.trim() : "";
    }

    public boolean isOptimizing() {
        return isOptimizing;
    }
}