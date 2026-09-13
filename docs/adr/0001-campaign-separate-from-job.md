# Campaign is separate from Job

A completed generation Job seeds a playable Campaign only when the host explicitly creates one. Job remains generation history (manuscript, sheets, persisted plan); Campaign owns Blueprint copy, roster, membership, and runtime. We rejected overloading Job as the live-play aggregate because it already mixes billing-era metadata, S3 keys, and async status.
