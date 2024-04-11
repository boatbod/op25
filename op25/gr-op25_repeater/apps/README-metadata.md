OP25 supports sending of metadata updates to an icecast streaming server. Configuration depends on which variant of op25 you are running; `rx.py` or `multi_rx.py`.

## `rx.py`

Make a local copy of meta.json (e.g. cp meta.json my_meta.json) and edit it so that it matches your streaming server mount point and password

```
    {
        "icecastPass": "password",
        "icecastMountpoint": "mountpoint",
        "icecastServerAddress": "server.name:port",
        "delay": "0.0", "icecastMountExt": ".m3u",
        "meta_format_idle": "[idle]",
        "meta_format_tgid": "[%TGID%]",
        "meta_format_tag":  "[%TGID%] %TAG%"
    }
```

Add the `-M my_meta.json` command line option to `rx.py`


## `multi_rx.py`

Metadata information is entered in the `metadata` section of the main `cfg.json` configuration file. Format and content is the same as used by `rx.py`

## Metatag Format

The user has some control over the format of the metadata presented to the streaming server. The following pieces of information are available:
- `%TGID%`: numeric talkgroup id
- `%TAG%`: descriptive talkgroup string (from `tgid-tags.tsv` file)

By modifying the content of the `meta_format_*` parameters you can customize the text for the three typical use cases.
- `meta_format_idle`: sent when op25 is idle/waiting for a call
- `meta_format_tgid`: sent during a call when only the tgid is known
- `meta_format_tag`: sent during a call when both tgid and tag are known

`%TGID%` and `%TAG%` will be substituted with the in-call data at runtime
