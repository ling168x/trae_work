package com.example.gamebooster;

import android.annotation.SuppressLint;
import android.app.Service;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.os.IBinder;
import android.util.Log;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.TextView;

import java.lang.reflect.Field;

public class FloatingController extends Service {

    private static final String TAG = "GameBooster";
    private WindowManager windowManager;
    private View floatingView;
    private TextView speedDisplay;
    private Button speedUpBtn;
    private Button speedDownBtn;
    private Button closeBtn;

    private float currentSpeed = 1.0f;
    private float maxSpeed = 10.0f;
    private float minSpeed = 0.5f;
    private float step = 0.5f;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createFloatingView();
    }

    @SuppressLint("InflateParams")
    private void createFloatingView() {
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);

        LayoutInflater inflater = LayoutInflater.from(this);
        floatingView = inflater.inflate(R.layout.floating_controller, null);

        speedDisplay = floatingView.findViewById(R.id.speed_display);
        speedUpBtn = floatingView.findViewById(R.id.speed_up_btn);
        speedDownBtn = floatingView.findViewById(R.id.speed_down_btn);
        closeBtn = floatingView.findViewById(R.id.close_btn);

        updateSpeedDisplay();

        speedUpBtn.setOnClickListener(v -> {
            currentSpeed += step;
            if (currentSpeed > maxSpeed) currentSpeed = maxSpeed;
            updateSpeedDisplay();
            applySpeed();
        });

        speedDownBtn.setOnClickListener(v -> {
            currentSpeed -= step;
            if (currentSpeed < minSpeed) currentSpeed = minSpeed;
            updateSpeedDisplay();
            applySpeed();
        });

        closeBtn.setOnClickListener(v -> {
            stopSelf();
        });

        floatingView.setOnTouchListener(new View.OnTouchListener() {
            private int initialX, initialY;
            private float initialTouchX, initialTouchY;

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch (event.getAction()) {
                    case MotionEvent.ACTION_DOWN:
                        initialX = params.x;
                        initialY = params.y;
                        initialTouchX = event.getRawX();
                        initialTouchY = event.getRawY();
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        params.x = initialX + (int) (event.getRawX() - initialTouchX);
                        params.y = initialY + (int) (event.getRawY() - initialTouchY);
                        windowManager.updateViewLayout(floatingView, params);
                        return true;
                }
                return false;
            }
        });

        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
                PixelFormat.TRANSLUCENT);

        params.gravity = Gravity.TOP | Gravity.START;
        params.x = 100;
        params.y = 100;

        this.params = params;
        windowManager.addView(floatingView, params);
    }

    private WindowManager.LayoutParams params;

    private void updateSpeedDisplay() {
        String speedText = String.format("%.1fx", currentSpeed);
        speedDisplay.setText(speedText);

        if (currentSpeed == 1.0f) {
            speedDisplay.setTextColor(getResources().getColor(R.color.gray));
        } else if (currentSpeed <= 2.0f) {
            speedDisplay.setTextColor(getResources().getColor(R.color.green));
        } else if (currentSpeed <= 4.0f) {
            speedDisplay.setTextColor(getResources().getColor(R.color.yellow));
        } else {
            speedDisplay.setTextColor(getResources().getColor(R.color.red));
        }
    }

    private void applySpeed() {
        try {
            Class<?> timeClass = Class.forName("UnityEngine.Time");
            if (timeClass != null) {
                try {
                    Field timeScaleField = timeClass.getDeclaredField("timeScale");
                    timeScaleField.setAccessible(true);
                    timeScaleField.set(null, currentSpeed);
                    Log.d(TAG, "Unity Time.timeScale set to: " + currentSpeed);
                } catch (NoSuchFieldException e) {
                    try {
                        Field[] fields = timeClass.getDeclaredFields();
                        for (Field field : fields) {
                            if (field.getType() == float.class) {
                                field.setAccessible(true);
                                field.set(null, currentSpeed);
                                Log.d(TAG, "Set float field: " + field.getName());
                            }
                        }
                    } catch (Exception ex) {
                        Log.e(TAG, "Failed to apply speed: " + ex.getMessage());
                    }
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Unity class not found, trying system time approach");
        }
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (floatingView != null) {
            windowManager.removeView(floatingView);
        }
    }

    public void setSpeed(float speed) {
        this.currentSpeed = speed;
        updateSpeedDisplay();
        applySpeed();
    }
}