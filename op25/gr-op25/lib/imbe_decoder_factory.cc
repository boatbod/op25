#include "dummy_imbe_decoder.h"
#include "imbe_decoder.h"
#include "offline_imbe_decoder.h"
#include "software_imbe_decoder.h"
#include "vc55_imbe_decoder.h"

#include <cstdlib>
#include <cstring>

imbe_decoder_sptr
imbe_decoder::make()
{
   imbe_decoder_sptr imbe;
   const char *imbe_type = getenv("IMBE");
   if(imbe_type) {
      if(strcasecmp(imbe_type, "offline") == 0) {
         imbe = imbe_decoder_sptr(new offline_imbe_decoder());
      } else if(strcasecmp(imbe_type, "soft") == 0) {
         imbe = imbe_decoder_sptr(new software_imbe_decoder());
      } else if(strcasecmp(imbe_type, "vc55") == 0) {
         imbe = imbe_decoder_sptr(new vc55_imbe_decoder());
      } else {
         imbe = imbe_decoder_sptr(new dummy_imbe_decoder());
      }
   } else {
      imbe = imbe_decoder_sptr(new software_imbe_decoder());
   }
   return imbe;
}
