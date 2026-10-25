# Stage 6 — приватные файлы, безопасность и retention

## Размещение

Ожидается структура SpaceWeb:

```
account/
  public_html/                 # только PHP endpoints и local JS/CSS
  private/
    config.php                 # existing secrets, never packaged
    collab/                    # services
    collaboration-files/       # 0700, не web directory
      .quota.lock              # 0600
      <random 64-hex ID>        # 0600, без исполняемого extension
  database/migrations/007_client_collaboration/
  scripts/migrate-collab.php
  scripts/check-collab-storage.php
```

Root вычисляется сервером из private services, не принимается из браузера. Realpath/symlink проверки запрещают смену storage directory. При web запросе storage внутри actual DOCUMENT_ROOT отклоняется. Нельзя публиковать private subtree, SQL, CLI scripts или customer blobs. Existing private/.htaccess дополнительно сохраняется; оно не заменяет размещение вне web root.

## Validation и serving

Allowlist: PDF, JPG/JPEG, PNG, WebP, DOCX, XLSX. Проверяются upload error/is_uploaded_file, фактический size, UTF-8 display name, отсутствие traversal/control characters/full_path, extension, server MIME и signature. Browser MIME не считается достоверным. PHP/executable/HTML/SVG/arbitrary archive отвергаются.

- Raster: Fileinfo + getimagesize MIME/signature, ≤12000 на сторону, ≤40 млн pixels.
- PDF: header/EOF + MIME; явное active JavaScript/launch/embedded content запрещается. Это не полноценный PDF parser или доказательство отсутствия вредоносности.
- OOXML: ZipArchive read-only inspection, без extraction на диск. Обязательные content-types/root relationships/main XML; no encryption, macros/bin/embeddings/ActiveX, traversal, duplicate member names, DTD/entities/external relationships. Только reviewed member types XML/rels/PNG/JPEG/WebP; embedded media MIME проверяется. Максимум 256 members, 5 MiB каждый, 20 MiB суммарно, compression ratio ≤200. Сложные, внешне связанные или нестандартные легитимные Office files могут отклоняться: дополнительные форматы/состав требуют security review.

**Malware scanning не настроен и не заявляется.** Format inspection не заменяет antivirus. Требуются PHP Fileinfo; для DOCX/XLSX также ZipArchive. Если extension отсутствует, контролируемый 503 вместо bypass. Raster image validation не требует GD. На SpaceWeb наличие extensions в этой задаче не проверялось.

Download сначала авторизует server session/project/visibility, затем проверяет private ID shape, symlink/missing bytes, фактический размер и SHA256. Возвращает attachment, nosniff, private no-store, UTF-8 encoded safe filename. Ни storage key, ни disk path не выдаются API. Internal/archived files и чужие IDs для клиента имеют тот же 404 body, что отсутствующий объект. HTML print escaped; raw message/document HTML не исполняется.

## Квоты и согласованность

Default: 5 MiB per file, 100 MiB total; configurable application caps до 10 MiB per file и 512 MiB total. Для хостинга 1 GB оставлен запас, но это НЕ измерение квоты всего аккаунта: другие сайты, почта, БД и backups учитываются хостером отдельно. Upload требует ещё ≥16 MiB physical free space. Эффективный лимит дополнительно ограничен host upload_max_filesize/post_max_size; их необходимо проверить до активации. PHP upload_progress не используется; прогресс — browser XHR upload events.

flock serializes quota + filesystem operations. Total считается по фактическим private files, включая unreferenced remnants, а не только metadata rows. Random IDs не переиспользуются, одинаковые display names не перезаписывают друг друга. Move + permission/size/hash verify происходят до DB commit. Если DB/history write не удаётся, транзакция откатывается, удаляется только созданный этим незавершённым upload blob. Успех возвращается только после commit.

Filesystem и MySQL не образуют distributed transaction: внезапное завершение процесса между move и commit может оставить **unreferenced private blob**, но не committed metadata, указывающую на неподтверждённый файл. Он учитывается в quota и не публикуется. Read-only CLI `check-collab-storage.php` показывает только counts/bytes/missing/corrupt/invalid/unreferenced; не экспортирует имён, keys или содержимого и ничего не удаляет. Проверенные storage failures не следует «лечить» массовым удалением.

## Retention и доступ

Архивирование project/document/revision/file логическое; данные/bytes и approval history не уничтожаются. Owner может явно изменить file visibility или archive, с optimistic version и audit; customer лишается доступа, но snapshot checksum/decision остаются. Пока pending review attachment недоступен, решение по нему не принимается. Messages/files этого проекта видны клиенту, shared upload из composer доступен после успешной загрузки даже до send; UI сообщает об этом.

Опубликованное содержимое revisions никогда не редактируется на месте; новые редакции сохраняют прежние bodies/files/checksums. Нет endpoint физического удаления принятых versions/decisions. Retention duration, legal erasure и безопасная purge-процедура требуют отдельного owner/legal решения; никакой юридической политики здесь не придумано и compliance не заявляется. Backup должен включать согласованный снимок БД **и** private storage с теми же IDs; восстановление одного без другого может дать missing-file 503.

Draft text messages хранится в sessionStorage вкладки по owner/customer + project; это не server log и не secret store, закрытие вкладки его удаляет. На общем устройстве нужно завершать сессию/закрывать вкладку. Документный черновик остаётся в открытой форме при network/API error; full reload может его потерять до явного сохранения draft в БД. Credentials, cookies и tokens не входят в activity records.

Никаких production storage reads/writes, host configuration changes, сканирования реальных customer files или migrations в этом ходе не выполнялось.
