### Initialize Stores
```
./groceries init-stores
```

### Update Store
```
./groceries update-store --name "Stew Leonards" --new-name "Stew Leonard's"
./groceries update-store --id 2 --website "https://stewleonards.com"
```

### Scrape
```
./groceries scrape --store stew-leonards
python scripts/processing/scrape_hmart.py
```


### Load Data
```
./groceries load-directory data/stage/hmart
```