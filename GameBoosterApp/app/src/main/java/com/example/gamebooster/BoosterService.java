package com.example.gamebooster;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

public class BoosterService extends Service {

    private static final String CHANNEL_ID = "GameBoosterChannel";
    private static final int NOTIFICATION_ID = 1;
    private PerformanceOptimizer optimizer;
    private int boostLevel;

    @Override
    public void onCreate() {
        super.onCreate();
        optimizer = new PerformanceOptimizer(this);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null) {
            boostLevel = intent.getIntExtra("level", 3);
        }

        startForeground(NOTIFICATION_ID, createNotification());
        
        optimizer.startOptimization(boostLevel);
        
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        optimizer.stopOptimization();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "游戏加速",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("游戏加速服务运行中");
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.createNotificationChannel(channel);
        }
    }

    private Notification createNotification() {
        String levelText;
        if (boostLevel == 1) {
            levelText = "省电模式";
        } else if (boostLevel == 2) {
            levelText = "平衡模式";
        } else {
            levelText = "高性能模式";
        }

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("游戏加速")
                .setContentText("已开启 - " + levelText)
                .setSmallIcon(R.drawable.ic_boost)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();
    }
}