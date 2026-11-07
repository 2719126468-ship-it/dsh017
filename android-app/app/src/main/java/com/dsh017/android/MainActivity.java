package com.dsh017.android;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.webkit.DownloadListener;
import android.webkit.HttpAuthHandler;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String START_URL = "http://127.0.0.1:8080/";
    private static final String[] LOCAL_PORTS = {"8080", "8084", "8091", "8092"};
    private static final int REQUEST_IMPORT_BACKUP = 4101;
    private static final int REQUEST_EXPORT_BACKUP = 4102;
    private static final long MAX_MIGRATION_ARCHIVE_BYTES = 512L * 1024L * 1024L;

    private final ExecutorService backendExecutor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private TextView statusView;
    private ProgressBar progressBar;
    private boolean backendReady = false;
    private boolean starting = false;
    private ApiKeyStore apiKeyStore;
    private File pendingExportArchive;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        apiKeyStore = new ApiKeyStore(this);
        buildLayout();
        if (hasExistingDatabase()) startBackend();
        else showFirstRunMigrationDialog();
    }

    private void buildLayout() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(23, 22, 20));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(14), 0, dp(8), 0);
        toolbar.setBackgroundColor(Color.rgb(23, 22, 20));

        TextView brand = new TextView(this);
        brand.setText("DSH017");
        brand.setTextColor(Color.rgb(250, 249, 245));
        brand.setTextSize(16);
        brand.setTypeface(null, android.graphics.Typeface.BOLD);
        toolbar.addView(brand, new LinearLayout.LayoutParams(0, dp(48), 1));

        Button keyButton = toolbarButton("API 设置");
        keyButton.setOnClickListener(v -> showApiKeyDialog());
        toolbar.addView(keyButton, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(36)));

        Button migrationButton = toolbarButton("数据");
        migrationButton.setOnClickListener(v -> showDataMigrationMenu());
        LinearLayout.LayoutParams migrationParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, dp(36));
        migrationParams.leftMargin = dp(6);
        toolbar.addView(migrationButton, migrationParams);

        Button reloadButton = toolbarButton("刷新");
        reloadButton.setOnClickListener(v -> {
            if (backendReady && webView != null) webView.reload();
            else if (!starting) showDataMigrationMenu();
        });
        LinearLayout.LayoutParams reloadParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, dp(36));
        reloadParams.leftMargin = dp(6);
        toolbar.addView(reloadButton, reloadParams);

        statusView = new TextView(this);
        statusView.setText("正在启动内置服务…");
        statusView.setTextColor(Color.rgb(190, 184, 174));
        statusView.setTextSize(11);
        statusView.setPadding(dp(14), dp(4), dp(14), dp(6));
        statusView.setBackgroundColor(Color.rgb(23, 22, 20));

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setIndeterminate(true);
        progressBar.setVisibility(View.VISIBLE);

        webView = new WebView(this);
        configureWebView();
        webView.addJavascriptInterface(new ProviderKeyBridge(), "DSHProviderKeys");

        root.addView(toolbar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(48)));
        root.addView(statusView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(progressBar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(2)));
        root.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
    }

    private Button toolbarButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextSize(11);
        button.setTextColor(Color.rgb(250, 249, 245));
        button.setAllCaps(false);
        button.setPadding(dp(8), 0, dp(8), 0);
        button.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(53, 50, 46)));
        return button;
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setLoadsImagesAutomatically(true);
        settings.setBlockNetworkImage(false);
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            settings.setSafeBrowsingEnabled(true);
        }
        webView.setBackgroundColor(Color.rgb(10, 10, 10));
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int progress) {
                progressBar.setProgress(progress);
                progressBar.setVisibility(progress >= 100 ? View.GONE : View.VISIBLE);
            }
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return routeNavigation(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return routeNavigation(Uri.parse(url));
            }

            @Override
            public void onReceivedHttpAuthRequest(WebView view, HttpAuthHandler handler,
                                                  String host, String realm) {
                // Local embedded services are loopback-only and should never prompt for credentials.
                handler.cancel();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    statusView.setText("页面加载失败。请检查内置服务状态后点“刷新”。");
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (backendReady) {
                    statusView.setText("内置服务运行中 · 数据保存在本机");
                }
            }
        });
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {
            Uri uri = Uri.parse(url);
            if ("https".equalsIgnoreCase(uri.getScheme())) {
                openExternal(uri);
            } else {
                Toast.makeText(this, "下载仅允许 HTTPS 地址", Toast.LENGTH_SHORT).show();
            }
        });
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
    }

    private boolean routeNavigation(Uri uri) {
        String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase();
        String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase();
        if ("about".equals(scheme)) return false;

        boolean localHost = "127.0.0.1".equals(host) || "localhost".equals(host);
        if ("http".equals(scheme) && localHost) {
            int port = uri.getPort();
            if (port < 0) port = 80;
            for (String allowed : LOCAL_PORTS) {
                if (String.valueOf(port).equals(allowed)) return false;
            }
            return true;
        }

        if ("https".equals(scheme)) {
            openExternal(uri);
            return true;
        }
        if ("mailto".equals(scheme) || "tel".equals(scheme)) {
            openExternal(uri);
            return true;
        }
        return true;
    }

    private void openExternal(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (Exception error) {
            Toast.makeText(this, "没有可打开此链接的应用", Toast.LENGTH_SHORT).show();
        }
    }

    private File appDataDirectory() {
        return new File(getFilesDir(), "dsh017");
    }

    private boolean hasExistingDatabase() {
        File database = new File(appDataDirectory(), "bili_data.db");
        return database.isFile() && database.length() > 0;
    }

    private void showFirstRunMigrationDialog() {
        new AlertDialog.Builder(this)
                .setTitle("导入旧版 DSH017 数据")
                .setMessage("如果你有从旧版导出的 .tar.gz 备份，可以先导入聊天记录、Workspace、收藏、预设和供应商配置。API Key 与 Android Keystore 密钥不会迁移，需要重新配置。")
                .setPositiveButton("选择备份文件", (dialog, which) -> openBackupPicker())
                .setNeutralButton("新建空白实例", (dialog, which) -> startBackend())
                .setOnCancelListener(dialog -> startBackend())
                .show();
    }

    private void showDataMigrationMenu() {
        if (backendReady) {
            new AlertDialog.Builder(this)
                    .setTitle("数据备份")
                    .setItems(new String[]{"导出备份文件"}, (dialog, which) -> createBackupArchive())
                    .setNegativeButton("取消", null)
                    .show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("数据迁移")
                .setItems(new String[]{"导入备份文件", "以空白数据启动"}, (dialog, which) -> {
                    if (which == 0) openBackupPicker();
                    else startBackend();
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void openBackupPicker() {
        if (backendReady || starting) {
            Toast.makeText(this, "导入必须在服务启动前进行；请勿覆盖当前数据", Toast.LENGTH_LONG).show();
            return;
        }
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_TITLE, "选择 DSH017 .tar.gz 备份文件");
        startActivityForResult(intent, REQUEST_IMPORT_BACKUP);
    }

    private void createBackupArchive() {
        if (!backendReady || starting) {
            Toast.makeText(this, "请先启动服务，再导出备份", Toast.LENGTH_SHORT).show();
            return;
        }
        statusView.setText("正在创建本地数据备份…");
        backendExecutor.execute(() -> {
            try {
                File outputDir = new File(getCacheDir(), "migration-export");
                if (!outputDir.exists() && !outputDir.mkdirs()) {
                    throw new IOException("无法创建备份临时目录");
                }
                File dataDir = appDataDirectory();
                File presetDir = new File(dataDir, "presets");
                String path = Python.getInstance().getModule("android_entry")
                        .callAttr("create_backup_archive", outputDir.getAbsolutePath(),
                                dataDir.getAbsolutePath(), presetDir.getAbsolutePath()).toString();
                File archive = new File(path);
                if (!archive.isFile() || archive.length() <= 0
                        || archive.length() > MAX_MIGRATION_ARCHIVE_BYTES) {
                    throw new IOException("备份文件不存在或超过 512 MB");
                }
                runOnUiThread(() -> {
                    pendingExportArchive = archive;
                    statusView.setText("备份已生成，请选择保存位置");
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("application/gzip");
                    intent.putExtra(Intent.EXTRA_TITLE, archive.getName());
                    startActivityForResult(intent, REQUEST_EXPORT_BACKUP);
                });
            } catch (Throwable error) {
                runOnUiThread(() -> {
                    statusView.setText("备份失败：" + shortError(error));
                    Toast.makeText(this, "备份失败：" + shortError(error), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void importBackup(Uri uri) {
        if (backendReady || starting) {
            Toast.makeText(this, "服务已经启动，拒绝覆盖现有应用数据", Toast.LENGTH_LONG).show();
            return;
        }
        starting = true;
        statusView.setText("正在读取并验证备份文件…");
        progressBar.setVisibility(View.VISIBLE);
        backendExecutor.execute(() -> {
            File archive = new File(getCacheDir(), "migration-import.tar.gz");
            try {
                try (InputStream input = getContentResolver().openInputStream(uri);
                     FileOutputStream output = new FileOutputStream(archive, false)) {
                    if (input == null) throw new IOException("无法打开所选备份文件");
                    copyBounded(input, output, MAX_MIGRATION_ARCHIVE_BYTES);
                    output.getFD().sync();
                }
                File dataDir = appDataDirectory();
                File presetDir = new File(dataDir, "presets");
                Python.getInstance().getModule("android_entry").callAttr(
                        "restore_backup_archive",
                        archive.getAbsolutePath(),
                        dataDir.getAbsolutePath(),
                        presetDir.getAbsolutePath());
                if (!new File(dataDir, "bili_data.db").isFile()) {
                    throw new IOException("恢复未生成预期的数据库文件");
                }
                archive.delete();
                runOnUiThread(() -> {
                    starting = false;
                    statusView.setText("备份已验证并恢复，正在启动内置服务…");
                    startBackend();
                });
            } catch (Throwable error) {
                archive.delete();
                runOnUiThread(() -> {
                    starting = false;
                    progressBar.setVisibility(View.GONE);
                    statusView.setText("导入失败：" + shortError(error));
                    new AlertDialog.Builder(this)
                            .setTitle("备份导入失败")
                            .setMessage(shortError(error) + "\n原有应用数据未被覆盖。你可以重新选择备份文件，或以空白实例启动。")
                            .setPositiveButton("重新选择", (dialog, which) -> openBackupPicker())
                            .setNeutralButton("新建空白实例", (dialog, which) -> startBackend())
                            .setNegativeButton("稍后", null)
                            .show();
                });
            }
        });
    }

    private void exportBackup(Uri uri) {
        File archive = pendingExportArchive;
        pendingExportArchive = null;
        if (archive == null || !archive.isFile()) {
            Toast.makeText(this, "备份临时文件已失效，请重新导出", Toast.LENGTH_LONG).show();
            return;
        }
        backendExecutor.execute(() -> {
            try (InputStream input = new java.io.FileInputStream(archive);
                 OutputStream output = getContentResolver().openOutputStream(uri, "w")) {
                if (output == null) throw new IOException("无法写入所选位置");
                copyBounded(input, output, MAX_MIGRATION_ARCHIVE_BYTES);
                output.flush();
                runOnUiThread(() -> Toast.makeText(this, "备份已保存", Toast.LENGTH_LONG).show());
            } catch (Throwable error) {
                runOnUiThread(() -> Toast.makeText(this, "保存备份失败：" + shortError(error), Toast.LENGTH_LONG).show());
            } finally {
                archive.delete();
            }
        });
    }

    private long copyBounded(InputStream input, OutputStream output, long maxBytes) throws IOException {
        byte[] buffer = new byte[8192];
        long total = 0;
        int read;
        while ((read = input.read(buffer)) != -1) {
            total += read;
            if (total > maxBytes) throw new IOException("备份文件超过 512 MB 限制");
            output.write(buffer, 0, read);
        }
        return total;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            if (requestCode == REQUEST_EXPORT_BACKUP && pendingExportArchive != null) {
                pendingExportArchive.delete();
                pendingExportArchive = null;
            }
            if (requestCode == REQUEST_IMPORT_BACKUP) {
                Toast.makeText(this, "未选择备份文件", Toast.LENGTH_SHORT).show();
            }
            return;
        }
        if (requestCode == REQUEST_IMPORT_BACKUP) {
            importBackup(data.getData());
        } else if (requestCode == REQUEST_EXPORT_BACKUP) {
            exportBackup(data.getData());
        }
    }

    private void startBackend() {
        if (starting || backendReady) return;
        starting = true;
        progressBar.setVisibility(View.VISIBLE);
        statusView.setText("正在启动内置 Python 服务（首次启动可能稍慢）…");
        backendExecutor.execute(() -> {
            try {
                File dataDir = new File(getFilesDir(), "dsh017");
                File presetDir = new File(dataDir, "presets");
                if (!presetDir.exists() && !presetDir.mkdirs()) {
                    throw new IOException("无法创建应用数据目录");
                }
                copyAssetDirectory("presets", presetDir);

                PyObject launcher = Python.getInstance().getModule("android_entry");
                launcher.callAttr("start_services",
                        dataDir.getAbsolutePath(),
                        presetDir.getAbsolutePath(),
                        apiKeyStore.read(),
                        apiKeyStore.readProviderKeysJson());
                boolean ready = launcher.callAttr("wait_ready", 60).toBoolean();
                String errors = launcher.callAttr("startup_errors").toString();

                runOnUiThread(() -> {
                    starting = false;
                    backendReady = ready;
                    progressBar.setVisibility(View.GONE);
                    if (ready) {
                        statusView.setText("四个本地服务已启动 · API Key 可在右上角配置");
                        webView.loadUrl(START_URL);
                    } else {
                        statusView.setText("服务启动未完成。 " + errors);
                        Toast.makeText(this, "服务启动超时，请点刷新重试", Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Throwable error) {
                runOnUiThread(() -> {
                    starting = false;
                    backendReady = false;
                    progressBar.setVisibility(View.GONE);
                    statusView.setText("启动失败：" + shortError(error));
                    Toast.makeText(this, "内置服务启动失败：" + shortError(error), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void copyAssetDirectory(String assetPath, File targetDirectory) throws IOException {
        if (!targetDirectory.exists() && !targetDirectory.mkdirs()) {
            throw new IOException("无法创建目录：" + targetDirectory);
        }
        String[] children = getAssets().list(assetPath);
        if (children == null) return;
        for (String child : children) {
            String childAsset = assetPath + "/" + child;
            String[] nested = getAssets().list(childAsset);
            File target = new File(targetDirectory, child);
            if (nested != null && nested.length > 0) {
                copyAssetDirectory(childAsset, target);
            } else if (!target.exists()) {
                try (InputStream input = getAssets().open(childAsset);
                     FileOutputStream output = new FileOutputStream(target)) {
                    byte[] buffer = new byte[8192];
                    int read;
                    while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
                }
            }
        }
    }

    private boolean isProviderSettingsPage() {
        if (webView == null) return false;
        String page = webView.getUrl();
        if (page == null) return false;
        try {
            Uri uri = Uri.parse(page);
            return "http".equalsIgnoreCase(uri.getScheme())
                    && "127.0.0.1".equalsIgnoreCase(uri.getHost())
                    && uri.getPort() == 8092
                    && "/providers".equals(uri.getPath())
                    && uri.getUserInfo() == null
                    && uri.getQuery() == null
                    && uri.getFragment() == null;
        } catch (Exception error) {
            return false;
        }
    }

    private final class ProviderKeyBridge {
        @JavascriptInterface
        public boolean save(String providerId, String apiKey) {
            if (!isProviderSettingsPage()) return false;
            if (providerId == null || apiKey == null || apiKey.length() > 4096) return false;
            if (!apiKeyStore.saveProviderKey(providerId, apiKey)) return false;
            backendExecutor.execute(() -> {
                try {
                    Python.getInstance().getModule("android_entry")
                            .callAttr("set_provider_key", providerId, apiKey == null ? "" : apiKey);
                } catch (Throwable ignored) {
                    // The encrypted key is persisted and will be loaded at next startup.
                }
            });
            return true;
        }
    }

    private void showApiKeyDialog() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(EditorInfo.TYPE_CLASS_TEXT | EditorInfo.TYPE_TEXT_VARIATION_PASSWORD);
        input.setHint("智谱 API Key（留空可清除）");
        input.setText(apiKeyStore.read());

        new AlertDialog.Builder(this)
                .setTitle("配置智谱 API Key")
                .setMessage("密钥只保存在此应用的私有空间，并由 Android Keystore 加密；不会传给 WebView 页面。")
                .setView(input)
                .setNegativeButton("取消", null)
                .setNeutralButton("清除", (dialog, which) -> saveApiKey(""))
                .setPositiveButton("保存", (dialog, which) -> saveApiKey(input.getText().toString().trim()))
                .show();
    }

    private void saveApiKey(String key) {
        try {
            apiKeyStore.save(key);
            backendExecutor.execute(() -> {
                try {
                    Python.getInstance().getModule("android_entry").callAttr("set_api_key", key);
                    runOnUiThread(() -> Toast.makeText(this,
                            key.isEmpty() ? "已清除 API Key" : "API Key 已保存",
                            Toast.LENGTH_SHORT).show());
                } catch (Throwable error) {
                    runOnUiThread(() -> Toast.makeText(this,
                            "密钥已保存，服务将在下次启动时读取", Toast.LENGTH_LONG).show());
                }
            });
        } catch (Exception error) {
            Toast.makeText(this, "无法安全保存 API Key：" + shortError(error), Toast.LENGTH_LONG).show();
        }
    }

    private String shortError(Throwable error) {
        String message = error.getMessage();
        if (message == null || message.trim().isEmpty()) message = error.getClass().getSimpleName();
        return message.length() > 180 ? message.substring(0, 180) : message;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            new AlertDialog.Builder(this)
                    .setMessage("退出 DSH017？本机数据会保留。")
                    .setNegativeButton("继续使用", null)
                    .setPositiveButton("退出", (dialog, which) -> finish())
                    .show();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
    }

    @Override
    protected void onPause() {
        if (webView != null) webView.onPause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.loadUrl("about:blank");
            webView.destroy();
            webView = null;
        }
        backendExecutor.shutdown();
        super.onDestroy();
    }
}
