import json
from difflib import get_close_matches as yaxin_sonuclari_getir

def veritabanini_yukle():
    with open('C:\\Users\\Amin\\Desktop\\VACIB!\\veritabani', 'r') as dosya:
        return json.load(dosya)

def veritabanina_yaz(veriler):
    with open('C:\\Users\\Amin\\Desktop\\VACIB!\\veritabani', 'w') as dosya:
        json.dump(veriler, dosya, indent = 2)

def yaxin_sonuclari_tap(sual, suallar):
    eyni = yaxin_sonuclari_getir(sual, suallar, n = 1, cutoff=0.6)
    return eyni[0] if eyni else None

def cavabini_tap(sual, veritabani):
    for sual_cavablar in veritabani['suallar']:
        if sual_cavablar['sual'] == sual:
            return sual_cavablar['cavab']
    return None

def chat_bot():
    veritabani = veritabanini_yukle()

    while True:
        sual = input('Siz: ')

        if sual == 'çıx':
            break

        gelen_sonuc = yaxin_sonuclari_tap(sual, [sual_cavablar['sual'] for sual_cavablar in veritabani['suallar']])

        if gelen_sonuc:
            verilecey_cavab = cavabini_tap(gelen_sonuc, veritabani)
            print(f'Bot: {verilecey_cavab}')
        else:
         print('Bot: Bunu nətər cavablayacağımı bilmirəm. Öyrədə bilərsiniz?')
         yeni_cavab = input("Öyrətmək üçün yazabilərsiniz və ya 'keç' diyəbilərsiniz.: '")

         if yeni_cavab != 'keç':
             veritabani['suallar'].append({
                 'sual': sual,
                 'cavab': yeni_cavab
             })
             veritabanina_yaz(veritabani)
             print('Bot: Təşəkkürlər sayənizdə yeni bir şey öyrəndim.')

if __name__ == '__main__':
    chat_bot()
