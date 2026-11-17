/* Native Windows linkage/allocation smoke test, not device audio or E2E acceptance. */
#include <opus.h>
#include <stdio.h>
int main(void) {
  for (int i=0;i<100;i++) {
    int err=0;
    OpusEncoder *encoder=opus_encoder_create(48000,1,OPUS_APPLICATION_VOIP,&err);
    if (!encoder || err != OPUS_OK) return 1;
    OpusDecoder *decoder=opus_decoder_create(48000,1,&err);
    if (!decoder || err != OPUS_OK) {opus_encoder_destroy(encoder);return 2;}
    opus_int16 input[960]={0},output[960]; unsigned char packet[4096];
    int length=opus_encode(encoder,input,960,packet,sizeof(packet));
    if (length<=0) return 3;
    if (opus_decode(decoder,packet,length,output,960,0)!=960) return 4;
    opus_decoder_destroy(decoder);opus_encoder_destroy(encoder);
  }
  puts("PASS 100 create/encode/decode/destroy cycles; no Windows GUI/device-audio claim");
  return 0;
}
