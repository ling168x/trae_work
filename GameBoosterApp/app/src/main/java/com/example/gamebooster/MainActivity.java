package com.example.gamebooster;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.Manifest;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;

public class MainActivity extends AppCompatActivity {

    private static final int REQUEST_PERMISSIONS_CODE = 1001;
    private static final int REQUEST_WRITE_SETTINGS_CODE = 1002;
    private static final int REQUEST_OVERLAY_CODE = 1003;

    private Switch boostSwitch;
    private TextView statusText;
    private TextView boostLevelText;
    private TextView rootStatusText;
    private TextView speedText;
    private SeekBar boostSlider;
    private SeekBar speedSlider;
    private Button optimizeBtn;

    private SharedPreferences prefs;
    private GameSpeedController speedController;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences("GameBooster", MODE_PRIVATE);
        speedController = new GameSpeedController(this);

        boostSwitch = findViewById(R.id.boost_switch);
        statusText = findViewById(R.id.status_text);
        boostLevelText = findViewById(R.id.boost_level_text);
        rootStatusText = findViewById(R.id.root_status_text);
        speedText = findViewById(R.id.speed_text);
        boostSlider = findViewById(R.id.boost_slider);
        speedSlider = findViewById(R.id.speed_slider);
        optimizeBtn = findViewById(R.id.optimize_btn);

        boolean isBoosting = prefs.getBoolean("is_boosting", false);
        boostSwitch.setChecked(isBoosting);
        updateStatus(isBoosting);
        updateRootStatus();

        int savedSpeed = prefs.getInt("game_speed", 1);
        speedSlider.setProgress(savedSpeed - 1);
        updateSpeedText(savedSpeed);

        boostSwitch.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                toggleBoost(isChecked);
            }
        });

        boostSlider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                updateBoostLevel(progress + 1);
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {}

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        updateBoostLevel(boostSlider.getProgress() + 1);

        optimizeBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                performOptimization();
            }
        });

        speedSlider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                int speed = progress + 1;
                updateSpeedText(speed);
                prefs.edit().putInt("game_speed", speed).apply();
                speedController.setSpeed(speed);
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {}

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        checkAndRequestPermissions();
    }

    private void checkAndRequestPermissions() {
        if (!hasAllPermissions()) {
            requestNecessaryPermissions();
        }
    }

    private boolean hasAllPermissions() {
        boolean hasInternet = ContextCompat.checkSelfPermission(this,
                Manifest.permission.INTERNET) == PackageManager.PERMISSION_GRANTED;
        boolean hasNetwork = ContextCompat.checkSelfPermission(this,
                Manifest.permission.ACCESS_NETWORK_STATE) == PackageManager.PERMISSION_GRANTED;
        boolean hasForeground = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                ContextCompat.checkSelfPermission(this,
                        Manifest.permission.FOREGROUND_SERVICE) == PackageManager.PERMISSION_GRANTED;
        boolean hasWriteSettings = Settings.System.canWrite(this);
        boolean hasOverlay = Settings.canDrawOverlays(this);

        return hasInternet && hasNetwork && hasForeground && hasWriteSettings && hasOverlay;
    }

    private void requestNecessaryPermissions() {
        requestBasicPermissions();
        
        if (!Settings.System.canWrite(this)) {
            requestWriteSettings();
        }

        if (!Settings.canDrawOverlays(this)) {
            requestOverlayPermission();
        }
    }

    private void requestBasicPermissions() {
        String[] permissions = {
                Manifest.permission.INTERNET,
                Manifest.permission.ACCESS_NETWORK_STATE,
                Manifest.permission.VIBRATE
        };

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions = new String[]{
                    Manifest.permission.INTERNET,
                    Manifest.permission.ACCESS_NETWORK_STATE,
                    Manifest.permission.VIBRATE,
                    Manifest.permission.FOREGROUND_SERVICE
            };
        }

        ActivityCompat.requestPermissions(this, permissions, REQUEST_PERMISSIONS_CODE);
    }

    private void requestWriteSettings() {
        Toast.makeText(this, "需要获取修改系统设置权限", Toast.LENGTH_LONG).show();
        Intent intent = new Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS);
        intent.setData(Uri.parse("package:" + getPackageName()));
        startActivityForResult(intent, REQUEST_WRITE_SETTINGS_CODE);
    }

    private void requestOverlayPermission() {
        Toast.makeText(this, "需要获取悬浮窗权限", Toast.LENGTH_LONG).show();
        Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION);
        intent.setData(Uri.parse("package:" + getPackageName()));
        startActivityForResult(intent, REQUEST_OVERLAY_CODE);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);

        if (requestCode == REQUEST_PERMISSIONS_CODE) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }

            if (allGranted) {
                Toast.makeText(this, "基础权限已获取", Toast.LENGTH_SHORT).show();
            } else {
                Toast.makeText(this, "部分权限未获取，功能可能受限", Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == REQUEST_WRITE_SETTINGS_CODE) {
            if (Settings.System.canWrite(this)) {
                Toast.makeText(this, "修改系统设置权限已获取", Toast.LENGTH_SHORT).show();
            } else {
                Toast.makeText(this, "未获取修改系统设置权限", Toast.LENGTH_SHORT).show();
            }
        } else if (requestCode == REQUEST_OVERLAY_CODE) {
            if (Settings.canDrawOverlays(this)) {
                Toast.makeText(this, "悬浮窗权限已获取", Toast.LENGTH_SHORT).show();
            } else {
                Toast.makeText(this, "未获取悬浮窗权限", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void toggleBoost(boolean enable) {
        Intent serviceIntent = new Intent(this, BoosterService.class);
        
        if (enable) {
            if (!android.provider.Settings.System.canWrite(this)) {
                boostSwitch.setChecked(false);
                Toast.makeText(this, "需要获取修改系统设置权限", Toast.LENGTH_LONG).show();
                requestWriteSettings();
                return;
            }
            
            int level = boostSlider.getProgress() + 1;
            serviceIntent.putExtra("level", level);
            ContextCompat.startForegroundService(this, serviceIntent);
            
            int speed = speedSlider.getProgress() + 1;
            if (speed > 1) {
                speedController.setSpeed(speed);
                boolean started = tryStartAcceleration();
                if (!started) {
                    boostSwitch.setChecked(false);
                    return;
                }
            }
            
            startFloatingController();
            
            prefs.edit().putBoolean("is_boosting", true).apply();
            Toast.makeText(this, String.format("游戏加速已开启 (x%d)", speed), Toast.LENGTH_SHORT).show();
        } else {
            stopService(serviceIntent);
            speedController.stopAcceleration();
            stopService(new Intent(this, FloatingController.class));
            prefs.edit().putBoolean("is_boosting", false).apply();
            Toast.makeText(this, "游戏加速已关闭", Toast.LENGTH_SHORT).show();
        }
        updateStatus(enable);
    }

    private boolean tryStartAcceleration() {
        long lastAttempt = prefs.getLong("last_root_attempt", 0);
        long now = System.currentTimeMillis();
        
        if (now - lastAttempt < 30000) {
            boolean cachedResult = prefs.getBoolean("root_access", false);
            if (!cachedResult) {
                Toast.makeText(this, "请先授予Root权限", Toast.LENGTH_LONG).show();
                return false;
            }
        }
        
        prefs.edit().putLong("last_root_attempt", now).apply();
        
        speedController.startAcceleration();
        
        if (!speedController.isAccelerating()) {
            prefs.edit().putBoolean("root_access", false).apply();
            Toast.makeText(this, "游戏加速启动失败，请检查Root权限", Toast.LENGTH_LONG).show();
            return false;
        }
        
        prefs.edit().putBoolean("root_access", true).apply();
        return true;
    }

    private Boolean hasRootCache = null;

    private boolean checkRootAccess() {
        if (hasRootCache != null) {
            return hasRootCache;
        }

        if (prefs.contains("root_access")) {
            hasRootCache = prefs.getBoolean("root_access", false);
            return hasRootCache;
        }

        boolean hasRoot = checkRootAccessInternal();
        hasRootCache = hasRoot;
        prefs.edit().putBoolean("root_access", hasRoot).apply();
        return hasRoot;
    }

    private boolean checkRootAccessInternal() {
        try {
            File suFile = new File("/system/bin/su");
            if (!suFile.exists()) {
                suFile = new File("/system/xbin/su");
            }
            if (!suFile.exists()) {
                return false;
            }

            java.lang.Process process = Runtime.getRuntime().exec(new String[]{"su", "-c", "id"});
            int exitCode = process.waitFor();
            return exitCode == 0;
        } catch (Exception e) {
            return false;
        }
    }

    private void clearRootCache() {
        hasRootCache = null;
        prefs.edit().remove("root_access").apply();
    }

    private void updateStatus(boolean isBoosting) {
        if (isBoosting) {
            statusText.setText(R.string.boost_enabled);
            statusText.setTextColor(getResources().getColor(R.color.green));
            boostSwitch.setText(R.string.boost_enabled);
        } else {
            statusText.setText(R.string.boost_disabled);
            statusText.setTextColor(getResources().getColor(R.color.red));
            boostSwitch.setText(R.string.boost_disabled);
        }
    }

    private void updateRootStatus() {
        boolean hasRoot = prefs.getBoolean("root_access", false);
        
        if (hasRoot) {
            rootStatusText.setText(R.string.root_available);
            rootStatusText.setTextColor(getResources().getColor(R.color.green));
        } else {
            rootStatusText.setText(R.string.root_unavailable);
            rootStatusText.setTextColor(getResources().getColor(R.color.yellow));
        }
    }

    private void updateSpeedText(int speed) {
        speedText.setText(String.format("x%d", speed));
        if (speed == 1) {
            speedText.setTextColor(getResources().getColor(R.color.gray));
        } else if (speed <= 3) {
            speedText.setTextColor(getResources().getColor(R.color.green));
        } else if (speed <= 5) {
            speedText.setTextColor(getResources().getColor(R.color.yellow));
        } else {
            speedText.setTextColor(getResources().getColor(R.color.red));
        }
    }

    private void startFloatingController() {
        if (android.provider.Settings.canDrawOverlays(this)) {
            startService(new Intent(this, FloatingController.class));
            Toast.makeText(this, "悬浮窗控制器已开启", Toast.LENGTH_SHORT).show();
        } else {
            Toast.makeText(this, "需要悬浮窗权限", Toast.LENGTH_LONG).show();
            requestOverlayPermission();
        }
    }

    private void updateBoostLevel(int value) {
        String level;
        if (value == 1) {
            level = getString(R.string.power_saving);
        } else if (value == 2) {
            level = getString(R.string.balanced);
        } else {
            level = getString(R.string.high_performance);
        }
        boostLevelText.setText(getString(R.string.boost_level) + ": " + level);
        prefs.edit().putInt("boost_level", value).apply();
    }

    private void performOptimization() {
        PerformanceOptimizer optimizer = new PerformanceOptimizer(this);
        optimizer.cleanMemory();
        optimizer.optimizeCPU();
        optimizer.optimizeNetwork();
        Toast.makeText(this, "系统优化完成", Toast.LENGTH_SHORT).show();
    }
}