# Gateway Runtime Wrapper

The production Go gateway source remains in `../../gateway-go` for compatibility
with existing imports and Dockerfiles. Build and test through this app folder
with:

```bash
go test ../../gateway-go/...
docker build -f ../../gateway-go/Dockerfile ../../gateway-go
```
