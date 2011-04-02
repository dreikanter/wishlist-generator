@set convert=d:\bin\imagemagick\convert
@set identify=d:\bin\imagemagick\identify
@set mogrify=d:\bin\imagemagick\mogrify
@rem %convert% ..\tmp\source.jpg -define filter:blur=0.75 -filter cubic -resize 300x300^> ..\tmp\source300-blur-cubic.jpg
@rem %identify% -format %%W,%%H\n ..\tmp\source300-blur-cubic.jpg ..\tmp\source.jpg
%identify% -format %%f,%%W,%%H\n D:\projects\wish.py\images\*
%mogrify% -define filter:blur=0.75 -filter cubic -resize 300x300^> D:\projects\wish.py\images\*
%identify% -format %%f,%%W,%%H\n D:\projects\wish.py\images\*