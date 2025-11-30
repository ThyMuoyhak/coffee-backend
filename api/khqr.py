from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
import schemas

router = APIRouter(prefix="/api/v1", tags=["khqr"])

@router.post("/khqr/generate", response_model=schemas.KHQRResponse)
def generate_khqr_payment(khqr_request: schemas.KHQRRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from main import KHQR_AVAILABLE, khqr, BAKONG_ACCOUNT
    
    if not KHQR_AVAILABLE:
        # Return demo data
        return schemas.KHQRResponse(
            qr_data="DEMO_QR_DATA",
            md5_hash="demo_md5_hash",
            deeplink="https://bakong.page.link/demo",
            qr_image=None
        )
    
    try:
        # Convert USD to KHR (approximate rate)
        exchange_rate = 4100  # 1 USD ≈ 4100 KHR
        amount_khr = int(khqr_request.amount * exchange_rate)
        
        # Generate QR code
        qr_data = khqr.create_qr(
            bank_account=BAKONG_ACCOUNT,
            merchant_name='BrewHaven Coffee',
            merchant_city='Phnom Penh',
            amount=amount_khr,
            currency='KHR',
            store_label='BrewHaven',
            phone_number='855123456789',
            bill_number=khqr_request.order_number,
            terminal_label='Online-Order',
            static=False
        )
        
        # Generate MD5 hash
        md5_hash = khqr.generate_md5(qr_data)
        
        # Generate deeplink
        deeplink = khqr.generate_deeplink(
            qr_data,
            callback=f"http://localhost:3000/order/{khqr_request.order_number}",
            appIconUrl="https://images.unsplash.com/photo-1509042239860-f550ce710b93?ixlib=rb-4.0.3&auto=format&fit=crop&w=100&q=80",
            appName="BrewHaven"
        )
        
        # Generate QR image (optional)
        qr_image = None
        try:
            qr_image = khqr.qr_image(qr_data, format='base64_uri')
        except Exception as e:
            print(f"QR image generation failed: {e}")
        
        return schemas.KHQRResponse(
            qr_data=qr_data,
            md5_hash=md5_hash,
            deeplink=deeplink,
            qr_image=qr_image
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KHQR generation failed: {str(e)}")

@router.get("/khqr/status/{order_number}", response_model=schemas.PaymentStatusResponse)
def get_payment_status(order_number: str, db: Session = Depends(get_db)):
    from main import KHQR_AVAILABLE, khqr
    import crud
    
    db_order = crud.get_order_by_number(db, order_number=order_number)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # For demo mode, return the stored status
    if not KHQR_AVAILABLE:
        return schemas.PaymentStatusResponse(
            order_number=order_number,
            payment_status=db_order.payment_status,
            transaction_data={"demo": True, "amount": db_order.total_amount}
        )
    
    transaction_data = None
    if db_order.khqr_md5 and db_order.khqr_md5 != "demo_md5_hash":
        try:
            transaction_data = khqr.get_payment(db_order.khqr_md5)
        except Exception as e:
            print(f"Error fetching transaction data: {e}")
    
    return schemas.PaymentStatusResponse(
        order_number=order_number,
        payment_status=db_order.payment_status,
        transaction_data=transaction_data
    )