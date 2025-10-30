BASENAME = frontend

MAIN_SOURCES = $(shell find ./src/ -maxdepth 2 -type f -name '*.py')

.PHONY: clean

all: control frontend.service postinst $(MAIN_SOURCES)
	mkdir -p $(BASENAME)/DEBIAN/
	mkdir -p $(BASENAME)/usr/local/bin/
	mkdir -p $(BASENAME)/lib/systemd/system/
	mkdir -p $(BASENAME)/etc/emulator/
	cp control postinst $(BASENAME)/DEBIAN/.
	cp frontend.service $(BASENAME)/lib/systemd/system/.
	cp config.json $(BASENAME)/etc/emulator/.
	cp -r src $(BASENAME)/usr/local/bin/frontend
	dpkg-deb --build $(BASENAME)

clean:
	rm -rf $(BASENAME) $(BASENAME).deb
