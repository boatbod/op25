#include "data_unit_handler.h"

data_unit_handler::~data_unit_handler()
{
}

void
data_unit_handler::handle(data_unit_sptr du)
{
   if(d_next) {
      d_next->handle(du);
   }
}

data_unit_handler::data_unit_handler(data_unit_handler_sptr next) :
   d_next(next)
{
}

