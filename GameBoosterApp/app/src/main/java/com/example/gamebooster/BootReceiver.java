package com.example.gamebooster;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

public class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            SharedPreferences prefs = context.getSharedPreferences("GameBooster", Context.MODE_PRIVATE);
            boolean isBoosting = prefs.getBoolean("is_boosting", false);
            
            if (isBoosting) {
                int level = prefs.getInt("boost_level", 3);
                Intent serviceIntent = new Intent(context, BoosterService.class);
                serviceIntent.putExtra("level", level);
                context.startForegroundService(serviceIntent);
            }
        }
    }
}