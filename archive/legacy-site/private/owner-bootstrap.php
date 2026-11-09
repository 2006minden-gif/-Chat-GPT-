<?php
declare(strict_types=1);
/** Read only the owner-authorized, hash-only first-login grant. Never stores a password/token. */
function owner_bootstrap_grant(): array {
    $raw=@file_get_contents(__DIR__.'/owner-bootstrap.json');
    $grant=$raw===false ? null : json_decode($raw,true);
    if (!is_array($grant) || ($grant['enabled']??false)!==true
        || !is_int($grant['expires_at']??null) || $grant['expires_at']<=time()
        || !is_string($grant['token_sha256']??null)
        || !preg_match('/^[a-f0-9]{64}$/D',$grant['token_sha256'])) return [];
    return $grant;
}
function owner_bootstrap_create(array $data): void {
    $grant=owner_bootstrap_grant();
    $token=$data['token']??null;
    if (!$grant || !is_string($token) || !preg_match('/^[a-f0-9]{64}$/D',$token)
        || !hash_equals($grant['token_sha256'],hash('sha256',$token)))
        fail(403,'Ссылка первого входа недействительна или истекла.','setup_unavailable');
    // Only the capability holder can reach password validation or writes.
    if (db()->query('SELECT id FROM nd_admin WHERE id=1')->fetchColumn())
        fail(409,'Кабинет уже создан. Войдите с вашим паролем.','owner_exists');
    rate('owner-bootstrap',10);
    $password=$data['password']??null;$repeat=$data['repeat']??null;
    if (!is_string($password) || !is_string($repeat) || !mb_check_encoding($password,'UTF-8')
        || strlen($password)<12 || strlen($password)>72 || $password!==$repeat)
        fail(422,'Пароли должны совпадать и содержать от 12 до 72 байт.','invalid_password');
    $hash=password_hash($password,PASSWORD_DEFAULT);
    try {
        // The primary key makes consumption atomic, including concurrent requests.
        // No UPDATE/REPLACE: an existing owner can never be reset by this grant.
        db()->prepare('INSERT INTO nd_admin (id,password_hash) VALUES (1,?)')->execute([$hash]);
    } catch(PDOException $e) {
        if ($e->getCode()==='23000')fail(409,'Кабинет уже создан. Войдите с вашим паролем.','owner_exists');
        throw $e;
    }
    json_response(['ok'=>true,'url'=>'/studio.php'],201);
}
