package com.dsh017.android;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.ByteBuffer;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class ApiKeyStore {
    private static final String ALIAS = "dsh017.provider.api.key";
    private static final String PREFS = "secure_provider_config";
    private static final String VALUE = "zhipu_api_key";
    private static final String PROVIDER_PREFIX = "provider_key_";
    private final SharedPreferences preferences;

    ApiKeyStore(Context context) {
        preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    synchronized String read() {
        String encoded = preferences.getString(VALUE, "");
        if (encoded == null || encoded.isEmpty()) return "";
        try {
            byte[] packed = Base64.decode(encoded, Base64.NO_WRAP);
            if (packed.length <= 12) return "";
            byte[] iv = new byte[12];
            byte[] ciphertext = new byte[packed.length - 12];
            System.arraycopy(packed, 0, iv, 0, 12);
            System.arraycopy(packed, 12, ciphertext, 0, ciphertext.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getKey(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(ciphertext), java.nio.charset.StandardCharsets.UTF_8);
        } catch (Exception error) {
            return "";
        }
    }

    synchronized void save(String value) throws Exception {
        if (value == null || value.isEmpty()) {
            preferences.edit().remove(VALUE).apply();
            return;
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getKey());
        byte[] iv = cipher.getIV();
        byte[] ciphertext = cipher.doFinal(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        ByteBuffer packed = ByteBuffer.allocate(iv.length + ciphertext.length);
        packed.put(iv);
        packed.put(ciphertext);
        preferences.edit().putString(VALUE, Base64.encodeToString(packed.array(), Base64.NO_WRAP)).apply();
    }

    synchronized String readProviderKeysJson() {
        org.json.JSONObject values = new org.json.JSONObject();
        for (String key : preferences.getAll().keySet()) {
            if (!key.startsWith(PROVIDER_PREFIX)) continue;
            String providerId = key.substring(PROVIDER_PREFIX.length());
            String encoded = preferences.getString(key, "");
            String decoded = decrypt(encoded);
            if (!decoded.isEmpty()) {
                try { values.put(providerId, decoded); } catch (org.json.JSONException ignored) {}
            }
        }
        return values.toString();
    }

    synchronized boolean saveProviderKey(String providerId, String value) {
        if (providerId == null || !providerId.matches("[a-z0-9][a-z0-9_-]{0,47}")) return false;
        String prefKey = PROVIDER_PREFIX + providerId;
        if (value == null || value.isEmpty()) {
            preferences.edit().remove(prefKey).apply();
            return true;
        }
        try {
            preferences.edit().putString(prefKey, encrypt(value)).apply();
            return true;
        } catch (Exception error) {
            return false;
        }
    }

    private String encrypt(String value) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getKey());
        byte[] iv = cipher.getIV();
        byte[] ciphertext = cipher.doFinal(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        ByteBuffer packed = ByteBuffer.allocate(iv.length + ciphertext.length);
        packed.put(iv);
        packed.put(ciphertext);
        return Base64.encodeToString(packed.array(), Base64.NO_WRAP);
    }

    private String decrypt(String encoded) {
        if (encoded == null || encoded.isEmpty()) return "";
        try {
            byte[] packed = Base64.decode(encoded, Base64.NO_WRAP);
            if (packed.length <= 12) return "";
            byte[] iv = new byte[12];
            byte[] ciphertext = new byte[packed.length - 12];
            System.arraycopy(packed, 0, iv, 0, 12);
            System.arraycopy(packed, 12, ciphertext, 0, ciphertext.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getKey(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(ciphertext), java.nio.charset.StandardCharsets.UTF_8);
        } catch (Exception error) {
            return "";
        }
    }

    private SecretKey getKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (keyStore.containsAlias(ALIAS)) {
            return (SecretKey) keyStore.getKey(ALIAS, null);
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }
}
