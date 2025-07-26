import { useNavigate } from 'react-router-dom';
import { XCircle, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const BillingCancel = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md text-center space-y-8">
        <XCircle className="w-16 h-16 mx-auto text-destructive" />

        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">Payment Cancelled</h1>
          <p className="text-muted-foreground">
            Your payment was cancelled and no charges were made.
          </p>
        </div>

        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            You can still use Airweave with limited features, or complete your subscription setup anytime from your organization settings.
          </p>

          <Button
            onClick={() => navigate('/')}
            className="w-full"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Continue to Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
};

export default BillingCancel;
