import secureStorage from "./secureStorage";

/**
 * "Beni hatırla" için saklanan giriş bilgileri.
 *
 * Native'de secureStorage Keychain/Keystore kullanır. Web'de böyle bir depo
 * yok, localStorage'a düşülüyor - yani şifre tarayıcıda düz metin durur ve
 * aynı kaynakta çalışan herhangi bir betik okuyabilir. Bu yüzden kayıt
 * VARSAYILAN OLARAK KAPALI; kullanıcı kutuyu işaretlemedikçe hiçbir şey
 * saklanmaz ve işareti kaldırdığında saklananlar silinir.
 */
const REMEMBER_KEY = "remember_me";
const EMAIL_KEY = "remembered_email";
const PASSWORD_KEY = "remembered_password";

export interface RememberedLogin {
  remember: boolean;
  email: string;
  password: string;
}

export async function loadRememberedLogin(): Promise<RememberedLogin> {
  const [remember, email, password] = await Promise.all([
    secureStorage.getItemAsync(REMEMBER_KEY),
    secureStorage.getItemAsync(EMAIL_KEY),
    secureStorage.getItemAsync(PASSWORD_KEY),
  ]);
  return {
    remember: remember === "1",
    email: email ?? "",
    password: password ?? "",
  };
}

export async function saveRememberedLogin(email: string, password: string): Promise<void> {
  await Promise.all([
    secureStorage.setItemAsync(REMEMBER_KEY, "1"),
    secureStorage.setItemAsync(EMAIL_KEY, email),
    secureStorage.setItemAsync(PASSWORD_KEY, password),
  ]);
}

export async function clearRememberedLogin(): Promise<void> {
  await Promise.all([
    secureStorage.deleteItemAsync(REMEMBER_KEY),
    secureStorage.deleteItemAsync(EMAIL_KEY),
    secureStorage.deleteItemAsync(PASSWORD_KEY),
  ]);
}
